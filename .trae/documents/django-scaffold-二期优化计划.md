# django-scaffold 二期优化计划

## 一、摘要

在一期工程骨架（config / utils / templates / static / deploy / CI）基础上完成 5 项优化：

1. **模板瘦身**：移除后台布局（`layouts/backend.html` 及其专属片段、`backend.css`），`templates/` 只保留前端内容；后台界面后续由三方库（推荐 django-unfold）适配。
2. **前端 UI 策略落地**：确定并实施 **Tailwind CSS v4.3 + DaisyUI 5 + Alpine.js 3 + HTMX 2** 的模板渲染友好技术栈；**不采用 shadcn/ui**（官方仅支持 React，与前后端不分离架构不兼容）。
3. **脚本与 Makefile**：新建 `scripts/`（init_data / export_database / import_database）+ 根目录 `Makefile`，实现一键安装、启动、构建、数据初始化、导入导出、lint、测试。
4. **安全简化**：移除 HTTPS 相关强安全配置（SSL 重定向、HSTS、Secure Cookie、代理协议头），保留 Django 默认零成本防护，降低毕设场景开发成本。
5. **Lint 规范集成**：以现有 ruff（PEP8 E/W + 扩展规则）为基础，补齐 `ruff format`、引入 pre-commit 钩子、CI 增加格式化检查，保证团队代码规范一致。

## 二、现状分析（已实地核查）

| 项 | 现状 |
| --- | --- |
| 目录 | `config/`、`utils/`、`templates/`、`static/`、`deploy/`、`tests/`、`.github/` 已就绪；`apps/`、`scripts/`、`database/`、`docs/` 未创建（本期只补 `scripts/` 与脚本所需的 `database/data/`） |
| 前端 | Tailwind **v3.4**（npm 构建，`tailwind.config.js` + `@tailwindcss/forms`），产物 `static/css/dist/base.css`；自定义 `.btn/.card` 组件类 |
| 模板 | `base.html` + `layouts/frontend.html` + `layouts/backend.html`；includes 7 个；后台专属：`sidebar.html`、`header.html` |
| 安全 | `base.py` 有 `SECURE_SSL_REDIRECT` env；`prod.py` 有完整 HTTPS 加固块（HSTS/Secure Cookie/代理头）；`.env.example` 含 `SECURE_SSL_REDIRECT` |
| Lint | `pyproject.toml` 已配置 ruff（E/F/W/I/N/UP/B/C4/SIM），`ruff check` 通过；**`ruff format --check` 有 2 个文件未通过**；无 pre-commit |
| 环境 | 本机默认 Node 16.13，但 nvm 已有 v22.18.0 / v25.8.2 可用；Docker 构建阶段为 `node:20-alpine` |
| 测试 | `tests/test_smoke.py` 参数化渲染 12 个模板，其中含待删除的 `backend.html`、`sidebar.html`、`header.html` |

## 三、UI 策略调研结论（用户重点关注项）

### 3.1 为什么不直接用 shadcn/ui

- shadcn/ui 官方**仅面向 React 生态**（Next.js、Vite、TanStack、React Router、Astro+React、Laravel），组件是「复制到项目中的 React 源码组件」，依赖 JSX/打包器，**无法在 Django 模板中渲染**。
- 强行引入 = 前后端分离 + React 构建链，直接违背本项目「前后端不分离、模板渲染」的定位，零基础成员开发成本陡增。
- 社区有非官方移植 **shadcn-django**（PyPI: `shadcn_django`），其实现方式恰好印证了正确路线：**Tailwind CSS + Alpine.js + HTMX** 的 HTML 组件。但该项目为非官方小众移植，不适合作为团队基座的稳定依赖，仅可作视觉参考。

### 3.2 最终策略：Tailwind v4 + DaisyUI + Alpine.js + HTMX

| 层 | 选型 | 理由 |
| --- | --- | --- |
| 样式引擎 | **Tailwind CSS v4.3**（`@tailwindcss/cli`） | 用户要求最前沿；v4 为最新稳定线，CSS-first 配置（可删掉 `tailwind.config.js`）、自动内容扫描、构建更快 |
| 组件库 | **DaisyUI 5** | Tailwind 插件（`@plugin "daisyui"`），**纯 CSS 类、零 JS 依赖**，与 Django 模板天然适配；官方提供 Django 安装文档；30+ 内置主题（含暗色），满足客户对 UI 的高要求；`btn` / `card` / `modal` / `alert` / `table` 等语义类对新手极其友好 |
| 交互 | **Alpine.js 3**（vendor 引入，~15KB） | HTML 属性式声明交互（下拉、弹窗、选项卡），与模板渲染同构思维，无需构建 |
| 动态请求 | **HTMX 2**（vendor 引入，~14KB） | 不写 JS 实现局部刷新/异步 CRUD，毕设类管理页面收益大 |
| 图标 | 内联 SVG（Heroicons/Lucide 复制粘贴） | 零依赖，仅在 README 约定用法 |

**开发成本结论**：该组合下业务开发只需在 Django 模板里写 CSS 类（如 `class="btn btn-primary"`、`class="card"`），无 React、无额外打包、无框架学习成本，与一期已建立的 Tailwind 管线一脉相承，是对零基础成员最友好的现代 UI 方案。

**参考来源**：
- shadcn/ui 仅支持 React：https://vercel.com/i/what-is-shadcn
- shadcn-django 非官方移植（Tailwind+Alpine+HTMX 路线佐证）：https://shadcn-django.com/ 、https://pypi.org/project/shadcn_django/
- Tailwind v4.3 与 Node≥20 要求、`@tailwindcss/cli`：https://tailwindcss.com/blog/tailwindcss-v4-3 、https://tailwindcss.zhcndoc.com/docs/upgrade-guide
- DaisyUI 5 支持 Tailwind v4 / 官方 Django 文档：https://daisyui.com/docs/v5/ 、https://daisyui.com/docs/install/django/

## 四、变更方案（按文件）

### 4.1 模板瘦身：移除后台布局

- **删除**：`templates/layouts/backend.html`、`templates/includes/sidebar.html`、`templates/includes/header.html`、`static/css/backend.css`。
- **修改 `tests/test_smoke.py`**：参数化列表移除 `layouts/backend.html`、`includes/sidebar.html`、`includes/header.html` 三项。
- **修改 `catalog.md`**：layouts 仅留 `frontend.html`（注释改为「前台页面布局；后台布局由三方管理主题适配」），includes 移除 sidebar/header 行，static/css 移除 backend.css 行，根目录补充 `Makefile` 条目。
- 后台三方库说明：仅在 README 中注明「后台管理界面后续由三方主题库适配（推荐 django-unfold，Tailwind 风格、与本前端栈统一）」，**本期不安装**。

### 4.2 前端 UI 栈升级到 Tailwind v4 + DaisyUI + Alpine + HTMX

- **`package.json`**：
  - devDependencies 改为 `tailwindcss@^4.3`、`@tailwindcss/cli@^4.3`、`daisyui@^5`；移除 `@tailwindcss/forms`（DaisyUI 提供表单组件类）。
  - scripts：`build`/`dev` 改用 `tailwindcss -i static/css/base.css -o static/css/dist/base.css`（v4 CLI bin 名仍为 `tailwindcss`，由 `@tailwindcss/cli` 提供；加 `--minify`）。
  - `engines.node` 改为 `>=20`。
- **删除 `tailwind.config.js`**（v4 CSS-first，内容自动扫描）。
- **新增 `.nvmrc`**：内容 `22`（本机 nvm 已有 v22.18.0）。
- **`static/css/base.css`** 迁移为 v4 语法：
  - 头部改为 `@import "tailwindcss";` + `@plugin "daisyui";`
  - `@layer base` 保留裸表单控件兜底样式（用原生 Tailwind 工具类重写，去掉对 @tailwindcss/forms 的依赖）。
  - `@layer components` 删除自定义 `.btn/.btn-primary/.btn-secondary/.card`（与 DaisyUI 同名类冲突，改用 DaisyUI），保留 `.form-error`。
- **模板类名迁移**（grep `btn-primary|btn-secondary|form-error|card` 全量核对）：`templates/errors/*.html`、`includes/confirm_modal.html`、`includes/messages.html`、`includes/pagination.html`、`includes/navbar.html`、`registration/password_reset_form.html` 中的自定义类替换为 DaisyUI 等价类（`btn btn-primary` / `btn btn-outline` / `card` / `alert` / `modal`）；confirm_modal 用 DaisyUI modal 结构 + 保留现有 `data-*` 钩子（`common.js` 逻辑不动）。
- **vendor 引入**（`static/vendor/`）：
  - `curl -L https://unpkg.com/alpinejs@3/dist/cdn.min.js -o static/vendor/alpine.min.js`
  - `curl -L https://unpkg.com/htmx.org@2/dist/htmx.min.js -o static/vendor/htmx.min.js`
  - （取当前最新稳定小版本，下载后校验非空且为 JS）
- **`templates/base.html`**：在 `base.js` 之前按序引入 `<script src="{% static 'vendor/htmx.min.js' %}" defer>`、`<script src="{% static 'vendor/alpine.min.js' %}" defer>`。
- **`deploy/Dockerfile`**：`node:20-alpine` → `node:22-alpine`；删除 `COPY tailwind.config.js ./` 行。
- **`.github/workflows/deploy.yml`**：`node-version: "20"` → `"22"`。

### 4.3 scripts/ 与 Makefile（一键执行）

- **新建 `scripts/init_data.py`**：
  - 独立可执行（`os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")` + `django.setup()`）。
  - argparse 支持 `--username/--password/--email`（默认 admin / admin123456 / admin@example.com）。
  - 幂等：超级用户已存在则跳过并提示；成功输出账号信息。
- **新建 `scripts/export_database.py`**：
  - 封装 `dumpdata`，排除 `contenttypes`、`auth.Permission`、`sessions`、`admin`；`--output` 默认 `database/data/export_YYYYmmdd_HHMMSS.json`，indent=2，自动建目录。
- **新建 `scripts/import_database.py`**：
  - 封装 `loaddata`；`--file` 缺省时取 `database/data/` 下最新 `.json`；执行前交互确认，`--yes` 跳过。
- **新建 `database/data/.gitkeep`**（脚本数据目录，不建其他文档）。
- **新建根目录 `Makefile`**（`.PHONY` + 自描述 `help` 默认目标，命令前缀 `uv run`）：
  - 环境与运行：`install`（uv sync + npm install）、`env`（.env 缺失时复制）、`run`（runserver 0.0.0.0:8000）、`check`
  - 前端：`css`（构建）、`css-watch`
  - 数据库：`migrate`、`makemigrations`、`superuser`、`init-data`、`export-db`、`import-db`
  - 质量：`lint`（ruff check）、`format`（ruff format + ruff check --fix）、`test`（pytest）、`hooks`（pre-commit install）
  - 部署：`docker-build`、`docker-up`、`docker-down`
  - 清理：`clean`（__pycache__、.pytest_cache、.ruff_cache）

### 4.4 移除 HTTPS 强安全配置

- **`config/settings/base.py`**：删除 `env()` 中 `SECURE_SSL_REDIRECT` 声明；删除「安全（基线）」小节（`SECURE_SSL_REDIRECT`、`X_FRAME_OPTIONS`，回退 Django 默认）。保留 `SecurityMiddleware`/`CsrfViewMiddleware`/`XFrameOptionsMiddleware`（Django 默认栈，零开发成本）。
- **`config/settings/dev.py`**：删除 `SECURE_SSL_REDIRECT = False` 及注释。
- **`config/settings/prod.py`**：删除整个「安全加固」块（`SECURE_PROXY_SSL_HEADER`、`SECURE_CONTENT_TYPE_NOSNIFF`、`SECURE_REFERRER_POLICY`、`X_FRAME_OPTIONS`、`SECURE_SSL_REDIRECT`、`SESSION_COOKIE_SECURE`、`CSRF_COOKIE_SECURE`、`SECURE_HSTS_*`）；docstring 去掉 HTTPS 开关说明。保留 MySQL、SMTP、日志配置。
- **`.env.example`**：删除 `SECURE_SSL_REDIRECT` 行及注释。
- **`deploy/nginx/default.conf`**：不动（本就是 HTTP 监听，基础响应头零成本）。
- **保留** `utils/security.py`（token/掩码等业务工具，与 HTTPS 无关）。

### 4.5 Lint 规范集成（PEP8）

- 保留现有 `[tool.ruff]` 配置（已覆盖 PEP8 E/W + isort/bugbear 等），不收紧也不放松。
- **立即执行** `uv run ruff format .` 修复当前 2 个未过格式化的文件。
- **`pyproject.toml`** dev 组新增 `pre-commit>=4.0`。
- **新建 `.pre-commit-config.yaml`**：
  - `astral-sh/ruff-pre-commit`：`ruff`（check）+ `ruff-format` 两个 hook
  - `pre-commit/pre-commit-hooks`：trailing-whitespace、end-of-file-fixer、check-yaml、check-toml、check-added-large-files
- **`.github/workflows/deploy.yml`**：Ruff lint 步骤后追加 `uv run ruff format --check .`。

### 4.6 文档同步

- **`README.md`**：
  - 技术栈表：前端样式行改为「Tailwind CSS v4 + DaisyUI 5 + Alpine.js + HTMX（模板渲染友好，无 React）」；Node 前置改为 ≥20（`nvm use`）。
  - 快速开始改为 `make install / make env / make css / make migrate / make run` 一键流程（保留手工命令对照）。
  - 常用命令段落替换为 Makefile 目标表。
  - 环境变量说明去掉 HTTPS 相关表述。
  - 新增简短「前端 UI 策略」小节：说明不采用 shadcn/ui 的原因与本方案（引用第三节结论，3-5 行即可）。
  - 注明后台管理界面后续由三方主题（推荐 django-unfold）适配。

## 五、假设与决策

1. **不采用 shadcn/ui**：官方 React-only，与模板渲染冲突；采用 DaisyUI 达成同级现代视觉（用户已授权我基于调研给出最佳策略）。
2. **Tailwind 升到 v4**：满足"最前沿"诉求；代价是 Node ≥20，本机 nvm 已具备、Docker 同步升级，风险可控。若执行时 npm 环境异常，回退方案为保留 v3.4 + DaisyUI 4（其余方案不变）。
3. **Alpine/HTMX 走 vendor 静态文件**而非 npm 打包：保持构建链"只编译 CSS"，新手零心智负担。
4. **后台三方库本期不装**：用户明确"后续三方库直接适配"，仅在文档记录推荐项 django-unfold。
5. **保留 Django 默认安全中间件与 CSRF**：移除的仅是 HTTPS 增强项；CSRF 是表单功能必需且零成本。
6. `dev.py` 中 `DEBUG = False` 为一期有意为之（本地预览自定义错误页），不在本期改动范围。
7. `apps/`、`docs/`、`database/` 完整内容属后续业务期，本期仅创建脚本必需的 `database/data/`。

## 六、验证步骤

1. **前端构建**：`nvm use 22 && npm install && npm run build` 成功；`grep -c "btn" static/css/dist/base.css` 有 DaisyUI 产物；产物被 `base.html` 引用。
2. **框架自检**：`uv run python manage.py check` 无错误。
3. **测试**：`uv run pytest` 全部通过（含更新后的模板渲染清单）。
4. **规范**：`uv run ruff check . && uv run ruff format --check .` 全部通过；`make hooks` 后提交触发 pre-commit。
5. **一键流程**：`make install && make env && make css && make migrate && make run` 起服；`/healthz/` 返回 ok；访问不存在路径看到 DaisyUI 风格 404 页。
6. **脚本**：`make init-data` 幂等创建超管并可登录 `/admin/`；`make export-db` 生成 `database/data/export_*.json`；`make import-db --yes` 回灌成功。
7. **安全简化**：`grep -ri "SECURE_SSL_REDIRECT\|SECURE_HSTS\|COOKIE_SECURE\|PROXY_SSL" config/ .env.example` 无残留。
8. **部署链（可选）**：`docker build -f deploy/Dockerfile -t django-scaffold .` 成功（Node 22 阶段完成 Tailwind v4 构建）。
