# django-scaffold 一键命令入口
# 用法：make <target>；直接执行 `make` 或 `make help` 查看全部命令。

UV ?= uv
NPM ?= npm
PYTHON := $(UV) run python
MANAGE := $(PYTHON) manage.py
COMPOSE := docker compose --env-file .env -f deploy/docker-compose.yml
APP_IMAGE ?= django-scaffold:local
# Celery 进程默认用 dev 配置（与 manage.py runserver 同源，读 .env 的 REDIS_URL）
DJANGO_SETTINGS_MODULE ?= config.settings.dev
export DJANGO_SETTINGS_MODULE

.DEFAULT_GOAL := help

.PHONY: help install env run check css css-watch migrate makemigrations superuser \
	init-data seed-data export-db import-db \
	lint format test \
	worker beat \
	docker-build docker-up docker-down \
	package clean

help: ## 显示全部可用命令
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ------------------------------ 环境与运行 ------------------------------

install: ## 安装 Python 与 Node 依赖
	$(UV) sync
	$(NPM) install

env: ## 生成 .env（不存在时从 .env.example 复制）
	@test -f .env || cp .env.example .env
	@echo ".env 已就绪"

run: ## 启动开发服务器（0.0.0.0:8000）
	$(MANAGE) runserver 0.0.0.0:8000

check: ## Django 框架自检
	$(MANAGE) check

# ------------------------------ 前端样式 ------------------------------

css: ## 构建 Tailwind CSS 和后台图表静态资源
	$(NPM) run build

css-watch: ## 监听模式构建 Tailwind CSS
	$(NPM) run dev

# ------------------------------ 数据库 ------------------------------

migrate: ## 应用数据库迁移
	$(MANAGE) migrate

makemigrations: ## 生成数据库迁移文件
	$(MANAGE) makemigrations

superuser: ## 交互式创建超级用户
	$(MANAGE) createsuperuser

init-data: ## 初始化基础数据（超级用户等，幂等）
	$(PYTHON) scripts/init_data.py

seed-data: ## 本地初始化业务种子数据（seeds/seed_data.yml；线上由中台统一触发）
	$(MANAGE) seedkit_run --trigger local --sync

export-db: ## 导出数据到 database/data/
	$(PYTHON) scripts/export_database.py

import-db: ## 导入 database/data/ 最近 fixture（FILE=路径 可指定，默认跳过确认）
	$(PYTHON) scripts/import_database.py $(if $(FILE),--file $(FILE),) --yes


# ------------------------------ 代码质量 ------------------------------

lint: ## 代码规范检查（ruff，PEP8）
	$(UV) run ruff check .

format: ## 代码格式化并自动修复
	$(UV) run ruff format .
	$(UV) run ruff check . --fix

test: ## 运行测试
	$(UV) run pytest

# ------------------------------ 异步任务（Celery）------------------------------

worker: ## 启动 Celery worker（本地开发；-P solo 避免 macOS 下 prefork 子进程报错）
	$(PYTHON) -m celery -A config worker -l INFO -P solo

beat: ## 启动 Celery beat 定时调度器（周期任务计划读自 Admin 数据库）
	$(PYTHON) -m celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler

# ------------------------------ 部署 ------------------------------

docker-build: ## 构建本地镜像（默认 tag 为 django-scaffold:local）
	docker build -f deploy/Dockerfile -t $(APP_IMAGE) .

docker-up: ## 启动容器编排（默认本地镜像，可用 APP_IMAGE=xxx make docker-up 指定）
	APP_IMAGE=$(APP_IMAGE) $(COMPOSE) up -d

docker-down: ## 停止并移除容器编排
	$(COMPOSE) down

# ------------------------------ 打包交付 ------------------------------

package: ## 打包项目源码为 zip
	@$(PYTHON) scripts/package.py

# ------------------------------ 清理 ------------------------------

clean: ## 清理缓存与中间产物
	@find . -type d -name __pycache__ -not -path "./.venv/*" -prune -exec rm -rf {} +
	@rm -rf .pytest_cache .ruff_cache
	@echo "缓存已清理"
