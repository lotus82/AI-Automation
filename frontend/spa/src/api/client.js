import axios from 'axios';
// Импортируем ваш стор Zustand (проверьте, чтобы путь ../store/bitrixAuthStore был правильным)
import { useBitrixAuthStore } from '../store/bitrixAuthStore';

const apiClient = axios.create({
    // Благодаря Vite proxy (в режиме разработки) и Nginx (на проде),
    // запросы на /api всегда будут уходить на правильный бэкенд
    baseURL: '/api',
});

// Добавляем интерцептор для автоматической подстановки заголовков Битрикс24
apiClient.interceptors.request.use(
    (config) => {
        // Достаем актуальные данные авторизации прямо из глобального стейта Zustand
        const { domain, appSid, extra } = useBitrixAuthStore.getState();
        
        // Вытаскиваем AUTH_ID из объекта extra (как это реализовал Cursor)
        const authId = extra?.AUTH_ID || '';

        // Если данные есть, прикрепляем их к заголовкам каждого запроса к FastAPI
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
    (error) => {
        return Promise.reject(error);
    }
);

export default apiClient;