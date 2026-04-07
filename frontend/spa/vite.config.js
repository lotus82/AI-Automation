import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
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
      // Перенаправляем все REST-запросы с /api на наш FastAPI бэкенд
      '/api': {
        target: 'http://web:8000',
        changeOrigin: true,
        ws: true, // Поддержка WebSocket (например, для /api/ws/monitoring)
      },
      // Перенаправляем голосовые сокеты
      '/voice': {
        target: 'http://web:8000',
        changeOrigin: true,
        ws: true,
      }
    }
  }
})