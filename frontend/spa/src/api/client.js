import axios from 'axios';
import { useAuthStore } from '../store/authStore.js';
import { useBitrixAuthStore } from '../store/bitrixAuthStore';

const apiClient = axios.create({
    // Благодаря Vite proxy (в режиме разработки) и Nginx (на проде),
    // запросы на /api всегда будут уходить на правильный бэкенд
    baseURL: '/api',
});

apiClient.interceptors.request.use(
    (config) => {
        const token = useAuthStore.getState().token;
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }

        const { user, settingsOrganizationId } = useAuthStore.getState();
        const orgScope = user?.organization_id ?? settingsOrganizationId;
        const urlPath = String(config.url || '');
        const needsOrg =
            orgScope &&
            (urlPath.includes('/settings') ||
                urlPath.includes('/knowledge') ||
                urlPath.includes('/shops') ||
                urlPath.includes('/mis') ||
                urlPath.includes('/questionnaires'));
        if (needsOrg) {
            const params = { ...(config.params || {}), organization_id: orgScope };
            config.params = params;
        }

        const { domain, appSid, extra } = useBitrixAuthStore.getState();
        const authId = extra?.AUTH_ID || '';

        if (domain) {
            config.headers['X-Bitrix-Domain'] = domain;
        }
        if (appSid) {
            config.headers['X-Bitrix-App-Sid'] = appSid;
        }
        if (authId) {
            config.headers['X-Bitrix-Auth-Id'] = authId;
        }

        return config;
    },
    (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
    (r) => r,
    (error) => {
        if (error?.response?.status === 401) {
            const reqUrl = String(error?.config?.url || '');
            if (reqUrl.includes('auth/login')) {
                return Promise.reject(error);
            }
            const path = window.location?.pathname || '';
            useAuthStore.getState().clearAuth();
            if (!path.startsWith('/login') && path !== '/') {
                window.location.assign('/login');
            }
        }
        return Promise.reject(error);
    }
);

export default apiClient;