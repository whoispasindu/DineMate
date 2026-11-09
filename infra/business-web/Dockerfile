FROM node:24-alpine AS build
RUN corepack enable
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY apps/student/package.json apps/student/
COPY apps/console/package.json apps/console/
COPY apps/business/package.json apps/business/
COPY packages/ui/package.json packages/ui/
COPY packages/api-client/package.json packages/api-client/
COPY e2e/package.json e2e/
RUN pnpm install --frozen-lockfile --filter "business..."
COPY packages/ui packages/ui
COPY packages/api-client packages/api-client
COPY apps/business apps/business
ENV VITE_API_URL=/api/v1
RUN pnpm --filter business build

FROM nginx:1.27-alpine
COPY infra/business-web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/apps/business/dist /usr/share/nginx/html
EXPOSE 8080
