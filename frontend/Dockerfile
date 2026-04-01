# Статическая панель + reverse proxy к FastAPI (сервис web в Docker Compose)
FROM nginx:alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY index.html tester.html scenarios.html telephony.html settings.html /usr/share/nginx/html/
COPY static /usr/share/nginx/html/static/

EXPOSE 80
