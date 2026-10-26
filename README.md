# django-scaffold

团队产品基座脚手架 —— 基于 Django 的工程化产品基座框架。

面向团队零基础新成员，结合内部 SOP 流程，快速搭建以「毕设主题业务」为主体的产品项目。
本仓库提供统一的目录结构、通用能力层（`utils`）、模板与静态资源体系、以及可本地运行、可容器化线上部署的工程基座。

## 技术栈与版本

| 组件 | 选型 | 说明 |
| --- | --- | --- |
| 语言 | Python 3.12 | 由 `uv` 自动拉取并锁定 |
| 框架 | Django 5.2 LTS | 服务端渲染 MVT 模式（前后端不分离） |
| 依赖/环境 | uv | `pyproject.toml` + `uv.lock` |
| 数据库 | SQLite(开发) / MySQL(生产) | 生产通过 PyMySQL 驱动 |
| 配置 | django-environ | `.env` 驱动，分环境 settings |
| 前端样式 | Tailwind CSS v4 + DaisyUI 5 | npm 构建，产物输出到 `static/css/dist/` |
| 前端交互 | Alpine.js 3 + HTMX 2 | vendor 本地引入，无需构建 |
| 代码规范 | ruff（PEP8） | `make lint` / `make format` |
| 异步任务 | Celery + Redis（云托管） | 耗时任务异步化；django-celery-beat（定时任务 Admin 管理）+ django-celery-results（结果落库），见 `docs/README.md` |
| 部署 | Docker + Gunicorn + WhiteNoise（ACR 镜像 + RDS 数据库） | 见 `deploy/` |

## 前端 UI 策略

本项目为前后端不分离的模板渲染架构，**不采用 shadcn/ui**（官方仅支持 React 生态，与 Django 模板不兼容）。
实际选型为对模板渲染最友好的现代组合：

- **Tailwind CSS v4**：原子化样式引擎，CSS-first 配置（无 `tailwind.config.js`，内容自动扫描）；
- **DaisyUI 5**：Tailwind 组件插件，`btn` / `card` / `modal` / `alert` / `table` 等语义类直接写进模板，30+ 内置主题；
- **Alpine.js + HTMX**：HTML 属性声明交互与局部刷新，业务页面无需手写 JS。

后台管理界面不使用自研布局，后续由三方主题库直接适配（推荐 [django-unfold](https://github.com/unfoldadmin/django-unfold)，Tailwind 风格、与本前端栈视觉统一）。

## 目录结构

```
django-scaffold/
├── manage.py               # 项目管理入口
├── Makefile                # 一键命令入口（make help 查看全部）
├── pyproject.toml          # 依赖与工具配置
├── package.json            # 前端构建链（Tailwind v4 + DaisyUI）
├── config/                 # 项目级配置（分环境 settings、urls、wsgi/asgi）
├── utils/                  # 项目级通用能力层（健壮、可扩展、易维护）
├── templates/              # 前端模板（base / layouts / includes / errors）
├── static/                 # 静态资源（Tailwind 源码与产物、js、vendor、images）
├── media/                  # 用户上传文件（不提交真实文件）
├── scripts/                # 辅助脚本（数据初始化、数据库导入导出）
├── database/               # 数据库交付材料（初始化/演示数据）
├── deploy/                 # 部署配置（Dockerfile / compose / entrypoint）
├── tests/                  # 框架级冒烟测试
└── .github/workflows/      # CI/CD 模板（按需使用）
```

> `apps/`、`docs/` 属于后续业务建设内容，当前步骤不创建。

## 快速开始（本地开发）

前置：已安装 [`uv`](https://docs.astral.sh/uv/) 与 Node.js **>= 20**（仓库含 `.nvmrc`，可用 `nvm use` 切换）。

```bash
make install      # 安装 Python + Node 依赖（等价于 uv sync && npm install）
make env          # 生成 .env（等价于 cp .env.example .env）
make css          # 构建 Tailwind 样式（等价于 npm run build）
make migrate      # 数据库迁移（开发默认 SQLite，零配置）
make init-data    # 初始化超级用户（admin / admin123456，幂等）
make run          # 启动开发服务器（等价于 uv run python manage.py runserver）
```

开发期样式监听：另开终端执行 `make css-watch`。

验证：

- 健康检查：<http://127.0.0.1:8000/healthz/> 返回 `{"status": "ok"}`
- 后台管理：<http://127.0.0.1:8000/admin/>（使用 `make init-data` 创建的账号登录）
- 访问任意不存在路径，将看到 DaisyUI 风格的 404 页面（验证模板 + Tailwind 管线）

## 环境变量说明

参见 `.env.example`。开发环境使用 SQLite 时无需配置数据库；生产环境通过 `DATABASE_URL`
或 `MYSQL_*` 变量指定 MySQL 连接，并务必设置强随机 `SECRET_KEY` 与正确的 `ALLOWED_HOSTS`。
本脚手架面向毕设等演示场景，默认纯 HTTP 部署，不含 HTTPS 相关开关。

## 常用命令（Makefile）

| 命令 | 说明 |
| --- | --- |
| `make install` / `make env` | 安装依赖 / 生成 .env |
| `make run` / `make check` | 启动开发服务器 / 框架自检 |
| `make css` / `make css-watch` | 构建 / 监听构建 Tailwind 样式 |
| `make migrate` / `make makemigrations` | 应用 / 生成数据库迁移 |
| `make init-data` | 初始化基础数据（超级用户，幂等） |
| `make export-db` / `make import-db` | 导出 / 导入数据库数据（`database/data/`） |
| `make lint` / `make format` | ruff 规范检查 / 格式化（PEP8） |
| `make test` | 运行测试（pytest） |
| `make worker` / `make beat` | 启动 Celery worker / beat 定时调度器（需先配好 `.env` 的 `REDIS_URL`） |
| `make docker-build` / `make docker-up` / `make docker-down` | 镜像构建 / 容器编排启停 |
| `make clean` | 清理缓存产物 |

## 线上部署

部署材料位于 `deploy/`，采用多阶段 Docker 构建（Node 22 阶段编译 Tailwind，Python 阶段运行 Gunicorn），
数据库使用阿里云 RDS 等第三方 MySQL，静态文件由 WhiteNoise 随应用直接提供（无需 Nginx）：

```bash
# 语法校验
docker compose --env-file .env -f deploy/docker-compose.yml config
# 构建镜像
make docker-build
```

`.github/workflows/deploy.yml` 负责构建并推送镜像到阿里云 ACR、更新服务器 `docker-compose.yml`、
拉取镜像重启并做容器健康检查（不设测试门禁）。镜像构建时会自动将 `.env.example` 复制为 `.env`，
应用启动时加载其中的配置，服务器无需维护环境变量文件。

## 分步建设规划

1. **基础框架**：工程骨架、通用能力层、模板与静态体系、本地运行与部署能力（已完成）。
2. **工程化优化**：前端 UI 栈（Tailwind v4 + DaisyUI）、Makefile/脚本、规范集成（本阶段）。
3. **通用业务模块**：用户认证（`apps/accounts`）、文件管理（`apps/files`）、操作日志（`apps/audit`，装饰器显式埋点、仅后台管理员可见）、消息通知（`apps/notifications`，站内信：定向/全站公告/事件自动通知 + 未读角标）均已完成；权限等分批建设中。
4. **示例业务模块**：`apps/demo` 端到端验证上述能力边界。
