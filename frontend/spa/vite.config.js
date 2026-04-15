import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const fileEnv = loadEnv(mode, process.cwd(), '')
  // В docker-compose.yml задано VITE_PROXY_TARGET=http://web:8000; на хосте без Docker — 127.0.0.1:8000
  const apiTarget =
    process.env.VITE_PROXY_TARGET || fileEnv.VITE_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      // 0.0.0.0 обязательно для того, чтобы сервер был доступен снаружи Docker-контейнера
      host: '0.0.0.0',
      port: 5173,
      watch: {
        // Включаем поллинг. Это критически важно для Docker (особенно на Windows/WSL),
        // иначе HMR не увидит, что вы сохранили файл, и страница не обновится
        usePolling: true,
      },
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          ws: true,
        },
        '/voice': {
          target: apiTarget,
          changeOrigin: true,
          ws: true,
        },
      },
    },
  }
})