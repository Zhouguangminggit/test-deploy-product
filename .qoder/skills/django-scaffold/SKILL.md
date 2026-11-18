---
name: django-scaffold
description: 基于 django-scaffold 产品基座创建或扩展毕设业务项目，复用 Django 通用模块、工具、工程化命令和 UI。用户要求基于本基座初始化项目、新增业务模块、接入认证/文件/审计/通知/异步任务，或要求遵循基座技术栈与代码规范时使用。
---

# django-scaffold 业务开发规范

## 核心原则

- **扩展基座，不重造基座**：优先复用现有 app、`utils/`、模板组件和 Make 命令。
- **以当前代码为准**：修改前阅读相近模块及配置，不凭空假设 API、目录或命令。
- **业务内聚**：一个业务主题对应 `apps/<module>/`，跨模块调用 service，不直接修改其他模块数据表。
- **小步交付**：实现功能时同步补齐迁移、测试内容，完成后执行验证。`。

## 批次协作方式

- 每批次业务开发开始前，主动向用户提问确认本批目标、页面、字段、业务流程、异常处理和验收标准；提供建议选项，已明确的信息不重复询问。
- 开发中出现影响需求、数据或交互的分支时及时确认，不擅自扩大本批范围。
- 批次交付包含种子数据检查与补齐，按下列流程完成。

## 批次种子数据交付

每批业务交付前，逐个检查本批新增或修改的模块，并同时完成模型数据与资源两项判断。以当前项目的 `docs/project/seed-data-guide.md`、Django 模型、迁移与实际种子配置为准。

1. **补齐模型数据。** 对新增或改动的模型、字典、状态和业务流程，在 `seeds/seed_data.yml` 或它引用的模块 YAML 中新增或更新本批所需的展示与初始化记录。纯基础设施、文档或修复批次若无需改种子，记录具体原因。没有图片的业务模块仍要检查并补齐结构化数据。
2. **补齐资源项。** 对有展示图片需求的模型，按真实字段配置 `images`。优先用 `keywords_from` 从本行或正向外键字段取词，按主题决定关键词，必要时用行级 `keywords` 覆盖。缺图保留业务记录并留日志，重跑可补图。无资源需求时只省略资源配置。
3. **验证配置准确性。** 对照模型检查必填字段、枚举、业务状态、唯一约束和数据权限。按目标主题组织代表性数据，用受数据库唯一约束保护的业务键配置 `match_by`，用 `ref` / `refs` 显式声明关系并让依赖先声明。避免写死跨环境的自增 ID。商品、分类和图片只是示例，字段、关系与关键词随项目定义。
4. **完成验收。** 至少校验配置可加载。涉及新关系或复杂规则时，在隔离测试库用模拟资源 API 覆盖预期关联、重复运行与错误回滚。领域校验或副作用依赖 service 时，用项目自己的受测初始化入口。交付记录已补模块及验证结果。按批交付只改配置和执行隔离测试，实际数据库填充由明确授权的初始化任务执行。

## 技术栈与固定约定

| 范围 | 约定 |
| --- | --- |
| 后端 | Python 3.12+、Django 5.2、函数视图、Django 模板 |
| 工程化 | uv + `pyproject.toml` + `uv.lock`；Make 作为统一命令入口 |
| 前端 | Node 22、Tailwind CSS v4、DaisyUI；样式产物由 `make css` 生成 |
| 数据 | 开发默认 SQLite，生产 MySQL；数据库变更必须提交 migrations |
| 异步 | Celery + Redis；周期任务由 django-celery-beat 管理，结果落库 |
| 质量 | pytest + pytest-django、Ruff；行宽 100，双引号，4 空格缩进 |
| 部署 | Docker Compose、Gunicorn、WhiteNoise；生产配置走环境变量 |

不要绕过 uv 直接使用 pip，不要手工修改 `uv.lock`，不要把 `static/css/dist/` 当源码编辑。

## 开发前定位

1. 阅读 `README.md`、`Makefile`、`pyproject.toml` 和 `.env.example`。
2. 阅读 `config/settings/`、`config/urls.py`，确认应用注册、路由与环境差异。
3. 参考最相近的现有模块；新增完整业务模块优先参考 `apps/accounts/` 或 `apps/files/`。
4. 新增通用函数前搜索 `utils/` 和各 app 的 `services.py`、`selectors.py`，避免重复实现。

## 业务模块分层

标准结构：`apps/<module>/{models,forms,services,selectors,views,urls,admin}.py`，按需增加 `tasks.py`、`migrations/`、`tests/`、`templates/<module>/`。

| 层 | 职责 |
| --- | --- |
| `models.py` | 数据结构、约束和模型级行为；用户外键使用 `settings.AUTH_USER_MODEL` |
| `forms.py` | 输入校验与表单展示，不承载跨模型业务流程 |
| `services.py` | 写操作、事务和跨模块副作用；多步写入使用 `transaction.atomic()` |
| `selectors.py` | 可复用查询、过滤和对象级访问范围；返回 QuerySet 或模型对象 |
| `views.py` | 解析请求、调用 form/service/selector、返回响应，不散落业务 SQL/ORM 写入 |
| `urls.py` | 声明 `app_name`，业务页面使用命名路由反解 |
| `admin.py` | 后台配置；普通模型使用 `utils.admin_theme.ModelAdmin` 兼容双主题 |
| `tasks.py` | 仅做 Celery 任务编排，核心逻辑仍放 service；传递主键等可序列化参数 |
| `tests/` | 覆盖正常流程、权限边界、校验失败和关键副作用 |

补充约束：

- 所有 `import` 统一放在文件顶部，禁止在函数或方法内部局部导入；遇到循环依赖优先调整依赖方向
- 视图默认使用函数视图；状态变更只接受 POST，并保留 CSRF 防护。
- 登录校验不等于数据权限；查询和详情操作必须限制本人或角色可见范围。
- 不在视图、模板或任务中绕过 service 直接执行带副作用的写操作。
- 跨模块复用时调用对方公开 service/selector，避免 GenericFK 和循环依赖。
- 代码风格、注释密度和命名与所在模块保持一致；注释解释原因，不复述代码。。

## 基座能力复用

| 需求 | 优先入口 | 注意事项 |
| --- | --- | --- |
| 登录、注册、资料、用户模型 | `apps.accounts` | 使用 Django auth 和 `get_user_model()`，不要新建 User 模型 |
| 文件上传、删除、权限查询 | `apps.files.services`、`apps.files.selectors` | 使用 `save_upload()`、`delete_file()` 及可访问文件查询，不绕过大小/扩展名校验 |
| 操作审计 | `apps.audit.decorators.log_operation` | 放在权限装饰器内侧；动作类型复用或扩展 `OperationAction` |
| 单用户通知、公告、已读 | `apps.notifications.services` | 业务事件调用通知 service，不直接创建收件记录 |
| 异步/定时任务 | 业务 app 的 `tasks.py` | 本地用 `make worker`、`make beat`；任务保持幂等并记录失败上下文 |
| 后端日志 | `from loguru import logger` | 不新增 `print` 或独立 logging 配置；不要记录密码、令牌和敏感内容 |
| 通用校验、权限、分页、图片等 | `utils/` | 先搜索复用；业务开发中识别到无业务耦合的通用能力可沉淀到 `utils/` 并补测试，不重复造轮子 |
| 前台页面 | `layouts/frontend.html`、`templates/includes/` | 复用导航、消息、分页、确认弹窗；使用 Tailwind/DaisyUI |
| 后台主题 | `ADMIN_UI=unfold/simpleui` | 不直接绑定某一主题 Admin 基类；必要时更新 `utils/admin_theme.py` 导航 |

调用具体函数前先阅读其签名与测试；新增可复用能力时同时补充成功、失败和权限测试。

## 环境、依赖与命令

- 公共配置放 `config/settings/base.py`；仅开发或生产的差异分别放 `dev.py`、`prod.py`。
- 新配置通过 `django-environ` 读取，提供合理默认值，并同步更新 `.env.example`。
- `.env` 只保存本地真实配置；不提交、不输出其中的密钥，`.env.example` 也不写真实凭据。
- 新增可复用工作流时更新 `Makefile` 和 `.PHONY`，保持 `make help` 可发现；一次性操作不必增加命令。

常用命令：

```bash
make env && make install       # 首次准备环境
make migrate && make init-data # 初始化数据库与基础数据

片）

make run                       # 开发服务
make css                       # 构建样式；持续开发用 make css-watch
make makemigrations            # 模型变化后生成迁移
make worker                    # 按需启动异步任务
make beat                      # 按需启动定时调度
make help                      # 查看完整命令
```

## 新增业务模块完成清单

- [ ] `apps.py` 使用 `name = "apps.<module>"`、`label = "<module>"`，并加入 `LOCAL_APPS`。
- [ ] 模型、迁移、service、selector、视图、路由、Admin 和模板职责清晰。
- [ ] `config/urls.py` 挂载模块路由，按需更新前台导航和后台导航。
- [ ] 用户关联、登录权限、对象级权限、POST/CSRF 和输入校验已处理。
- [ ] 文件、审计、通知、日志、异步任务均通过既有入口接入。
- [ ] 新环境变量、依赖和 Make 命令已同步，`docs/project/` 已按本批变更简要增量更新；无真实密钥或本地产物入库。
- [ ] 测试覆盖核心流程、异常与越权场景。
- [ ] **种子数据**：逐模块完成模型数据与资源判断，补齐所需 YAML 记录及关键词配置，并核对关联与验收结果。无需变更时记录原因。

## 每批次交付验证

每批次任务完成后、进入下一批次或交付前，按变更范围按需执行，不能只声明完成而不验证：

```bash
make format
make lint
make check
make test
make css        # 涉及模板或样式时
```

模型变更还需生成并应用迁移；涉及部署时检查 `deploy/` 与生产环境变量。若某项无法执行，明确说明原因及未覆盖风险。
