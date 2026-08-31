FROM node:20-alpine AS builder
WORKDIR /app
COPY app/web/package.json ./
RUN npm install --no-audit --no-fund
COPY app/web ./
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY app/web/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
