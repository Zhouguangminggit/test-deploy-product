# django-scaffold 一键命令入口
# 用法：make <target>；直接执行 `make` 或 `make help` 查看全部命令。

UV ?= uv
NPM ?= npm
PYTHON := $(UV) run python
MANAGE := $(PYTHON) manage.py
COMPOSE := docker compose -f deploy/docker-compose.yml

.DEFAULT_GOAL := help

.PHONY: help install env run check css css-watch migrate makemigrations superuser \
	init-data export-db import-db lint format test \
	docker-build docker-up docker-down clean

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

css: ## 构建 Tailwind CSS（产物 static/css/dist/base.css）
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

# ------------------------------ 部署 ------------------------------

docker-build: ## 构建 Docker 镜像
	docker build -f deploy/Dockerfile -t django-scaffold .

docker-up: ## 启动容器编排（deploy/docker-compose.yml）
	$(COMPOSE) up -d --build

docker-down: ## 停止并移除容器编排
	$(COMPOSE) down

# ------------------------------ 清理 ------------------------------

clean: ## 清理缓存与中间产物
	@find . -type d -name __pycache__ -not -path "./.venv/*" -prune -exec rm -rf {} +
	@rm -rf .pytest_cache .ruff_cache
	@echo "缓存已清理"
