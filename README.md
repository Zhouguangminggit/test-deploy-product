# django-scaffold

团队产品基座脚手架 —— 基于 Django 的工程化产品基座框架。

面向团队零基础新成员，结合内部 SOP 流程，快速搭建以「毕设主题业务」为主体的产品项目。
本仓库提供统一的目录结构、通用能力层（`utils`）、模板与静态资源体系、以及可本地运行、可容器化线上部署的工程基座。

## 技术栈与版本

| 组件 | 选型 | 说明 |
| --- | --- | --- |
| 语言 | Python 3.12 | 由 `uv` 自动拉取并锁定 |
| 框架 | Django 5.2 LTS | 服务端渲染 MVT 模式 |
| 依赖/环境 | uv | `pyproject.toml` + `uv.lock` |
| 数据库 | SQLite(开发) / MySQL(生产) | 生产通过 PyMySQL 驱动 |
| 配置 | django-environ | `.env` 驱动，分环境 settings |
| 前端样式 | Tailwind CSS v3.4 | npm 构建，产物输出到 `static/css/dist/` |
| 部署 | Docker + Gunicorn + Nginx | 见 `deploy/` |

## 目录结构（第一步：基础框架）

```
django-scaffold/
├── manage.py               # 项目管理入口
├── pyproject.toml          # 依赖与工具配置
├── config/                 # 项目级配置（分环境 settings、urls、wsgi/asgi）
├── utils/                  # 项目级通用能力层（健壮、可扩展、易维护）
├── templates/              # 全局模板（base / layouts / includes / errors）
├── static/                 # 静态资源（Tailwind 源码与构建产物、js、images、vendor）
├── media/                  # 用户上传文件（不提交真实文件）
├── deploy/                 # 部署配置（Dockerfile / compose / nginx / entrypoint）
├── tests/                  # 框架级冒烟测试
└── .github/workflows/      # CI/CD 模板（按需使用）
```

> `apps/`、`database/`、`docs/`、`scripts/` 属于第二、三步内容，本步骤不创建。

## 快速开始（本地开发）

前置：已安装 [`uv`](https://docs.astral.sh/uv/) 与 Node.js（>= 16.18）。

```bash
# 1. 安装 Python 依赖并创建虚拟环境（自动生成 uv.lock）
uv sync

# 2. 准备环境变量
cp .env.example .env

# 3. 安装前端依赖并构建 Tailwind 样式
npm install
npm run build          # 一次性构建；开发时可用 `npm run dev` 开启监听

# 4. 数据库迁移（开发默认 SQLite，零配置）
uv run python manage.py migrate

# 5. 启动开发服务器
uv run python manage.py runserver
```

验证：

- 健康检查：<http://127.0.0.1:8000/healthz/> 返回 `{"status": "ok"}`
- 后台管理：<http://127.0.0.1:8000/admin/>（首次需 `uv run python manage.py createsuperuser`）
- 访问任意不存在路径，将看到样式化的 404 页面（验证模板 + Tailwind 管线）

## 环境变量说明

参见 `.env.example`。开发环境使用 SQLite 时无需配置数据库；生产环境通过 `DATABASE_URL`
或 `MYSQL_*` 变量指定 MySQL 连接，并务必设置强随机 `SECRET_KEY` 与正确的 `ALLOWED_HOSTS`。

## 常用命令

```bash
uv run python manage.py check        # 框架自检
uv run python manage.py collectstatic # 收集静态文件（部署用）
uv run pytest                        # 运行测试
uv run ruff check .                  # 代码检查
uv run ruff format .                 # 代码格式化
```

## 线上部署

部署材料位于 `deploy/`，采用多阶段 Docker 构建（Node 阶段编译 Tailwind，Python 阶段运行 Gunicorn），
并由 Nginx 反向代理与提供静态/媒体文件：

```bash
# 语法校验
docker compose -f deploy/docker-compose.yml config
# 构建镜像
docker build -f deploy/Dockerfile -t django-scaffold .
```

`.github/workflows/deploy.yml` 提供了从检查、测试、构建镜像到部署的 CI/CD 模板（按需启用并填充密钥）。

## 分步建设规划

1. **基础框架**（本步骤）：工程骨架、通用能力层、模板与静态体系、本地运行与部署能力。
2. **通用业务模块**：文件上传下载、用户认证、权限、操作日志等。
3. **示例业务模块**：`apps/demo` 端到端验证上述能力边界。
