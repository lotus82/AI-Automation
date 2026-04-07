# Статическая панель + reverse proxy к FastAPI (сервис web в Docker Compose)
FROM nginx:alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY spa/dist/ /usr/share/nginx/html/

EXPOSE 80
