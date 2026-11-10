# syntax=docker/dockerfile:1
# ==============================================================================
# 多阶段构建：
#   阶段一（frontend-builder）：使用 Node 编译 Tailwind 静态资源
#   阶段二（runtime）：使用 uv 安装 Python 依赖并运行 Gunicorn
# 构建上下文为项目根目录：docker build -f deploy/Dockerfile -t django-scaffold .
# ==============================================================================

# ------------------------- 阶段一：前端资源构建 -------------------------
FROM node:22-alpine AS frontend-builder

WORKDIR /app

# 先装依赖以利用构建缓存（package-lock.json 可选）
COPY package.json package-lock.json* ./
RUN npm ci || npm install

# Tailwind v4 自动扫描项目内容生成用到的类（CSS-first 配置，无需 tailwind.config.js）
COPY static/ ./static/
COPY templates/ ./templates/
COPY apps/ ./apps/
COPY utils/ ./utils/

# 产物输出到 /app/static/css/dist/base.css
RUN npm run build


# --------------------------- 阶段二：应用运行时 ---------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# 从官方镜像获取 uv 二进制
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 先安装依赖（仅生产依赖，不安装项目自身），最大化利用缓存
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 拷贝项目代码（.dockerignore 已排除 .venv / node_modules 等）
COPY . .

# 构建时生成运行时 .env：将示例配置复制为 .env，供 django-environ 启动时加载
RUN cp .env.example .env

# 覆盖前端构建产物（放在 COPY . . 之后，避免被宿主机的旧产物覆盖）
COPY --from=frontend-builder /app/static/css/dist ./static/css/dist
COPY --from=frontend-builder /app/static/js/dist ./static/js/dist

# 预建运行时可写目录并降权到非 root 用户
RUN mkdir -p /app/staticfiles /app/media \
    && useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

ENV PATH="/app/.venv/bin:$PATH"

USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/deploy/entrypoint.sh"]
