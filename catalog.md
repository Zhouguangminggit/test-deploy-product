



```
django-scaffold/
│
├── manage.py                              # Django 项目管理入口
├── Makefile                              # 一键命令入口（make help 查看全部）
├── pyproject.toml                         # 项目依赖与工具配置
├── uv.lock                                # 依赖锁定文件
├── package.json                          # 前端构建链（Tailwind v4 + DaisyUI）
├── .nvmrc                                # Node 版本约定（>= 20）
├── .python-version                       # Python 版本
├── .env.example                          # 环境变量示例，不包含真实密钥
├── .gitignore                            # Git 忽略规则
├── README.md                             # 项目介绍、启动方式、框架版本
│
├── config/                               # Django 项目配置
│   ├── __init__.py
│   ├── urls.py                            # 项目级路由入口
│   ├── asgi.py                            # ASGI 服务入口
│   ├── wsgi.py                            # WSGI 服务入口
│   │
│   └── settings/                         # 环境配置目录
│       ├── __init__.py
│       ├── base.py                        # 公共配置
│       ├── dev.py                         # 本地开发配置
│       └── prod.py                        # 生产环境配置
│
├── apps/                                 # Django 应用目录
│   │
│   ├── accounts/                         # 用户账户模块
│   │   ├── __init__.py
│   │   ├── apps.py                        # App 注册配置
│   │   ├── models.py                      # 用户模型、用户扩展信息
│   │   ├── forms.py                       # 登录、注册、用户编辑表单
│   │   ├── urls.py                        # 账户模块路由
│   │   ├── views.py                       # 请求处理与页面渲染
│   │   ├── services.py                    # 注册、登录、账户操作逻辑
│   │   ├── selectors.py                   # 用户查询逻辑
│   │   ├── admin.py                       # Django Admin 配置
│   │   ├── migrations/                    # 数据库迁移文件
│   │   ├── tests/                         # 账户模块测试
│   │   │   └── __init__.py
│   │   └── templates/
│   │       └── accounts/                  # 账户模块页面模板
│   │           ├── login.html
│   │           ├── register.html
│   │           └── profile.html
│   │
│   │
│   ├── files/                            # 文件管理模块
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py                      # 文件记录、文件元数据
│   │   ├── forms.py                       # 文件上传表单
│   │   ├── urls.py                        # 文件模块路由
│   │   ├── views.py                       # 上传、下载请求处理
│   │   ├── services.py                    # 文件上传、删除、关联逻辑
│   │   ├── selectors.py                   # 文件查询逻辑
│   │   ├── admin.py
│   │   ├── migrations/
│   │   ├── tests/
│   │   │   └── __init__.py
│   │   └── templates/
│   │       └── files/                     # 文件管理页面
│   │
│   ├── audit/                            # 操作日志模块（按需启用）
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py                      # 操作日志模型
│   │   ├── services.py                    # 日志记录逻辑
│   │   ├── selectors.py                   # 日志查询逻辑
│   │   ├── admin.py
│   │   ├── migrations/
│   │   └── tests/
│   │       └── __init__.py
│   │
│   ├── seedkit/                          # 业务数据初始化基座（统一 YAML 驱动，中台/本地共用）
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py                      # SeedRun 运行记录 / SeedRunLog 逐条日志
│   │   ├── enums.py                       # 触发方式 / 状态 / 日志级别枚举
│   │   ├── loader.py                      # seed_data.yml 加载 + Schema 校验（fail-fast）
│   │   ├── engine.py                      # 写库引擎（ref 解析 / 图片分配 / 幂等 / refresh）
│   │   ├── services.py                    # 运行编排与状态流转（日志双写 DB + loguru）
│   │   ├── selectors.py                   # 运行记录 / 日志查询
│   │   ├── tasks.py                       # Celery 任务编排
│   │   ├── admin.py                       # 只读查看运行记录 + 日志内联
│   │   ├── management/
│   │   │   └── commands/                  # seedkit_run（触发）/ seedkit_status（查询）
│   │   ├── migrations/
│   │   └── tests/
│   │
│   └── demo/                             # 示例业务模块，可替换
│       ├── __init__.py
│       ├── apps.py
│       ├── models.py                      # 示例业务模型
│       ├── forms.py                       # 示例业务表单
│       ├── urls.py                        # 示例业务路由
│       ├── views.py                       # 示例业务页面
│       ├── services.py                    # 示例业务操作逻辑
│       ├── selectors.py                   # 示例业务查询逻辑
│       ├── admin.py
│       ├── migrations/
│       ├── tests/
│       │   └── __init__.py
│       └── templates/
│           └── demo/                      # 示例业务页面模板
│
├── utils/                                # 项目级公共工具目录
│   ├── __init__.py
│   ├── constants.py                      # 全局常量
│   ├── enums.py                          # 通用枚举
│   ├── exceptions.py                     # 自定义通用异常
│   ├── validators.py                     # 通用校验器
│   ├── decorators.py                     # 通用装饰器
│   ├── pagination.py                     # 通用分页处理
│   ├── middleware.py                     # 通用中间件
│   ├── context_processors.py             # 模板全局上下文处理
│   ├── permissions.py                    # 通用权限辅助函数
│   ├── response.py                       # 通用响应辅助方法
│   ├── helpers.py                        # 通用辅助函数
│   ├── date_time.py                      # 日期时间处理工具
│   ├── file_helpers.py                   # 文件名、文件大小等处理
│   ├── image_helpers.py                  # 图片处理工具
│   ├── pixabay.py                        # Pixabay 图片检索下载客户端（seedkit 数据初始化用）
│   ├── security.py                       # 安全相关辅助方法
│   │
│   └── templatetags/                     # Django 自定义模板标签
│       ├── __init__.py
│       └── common_tags.py                # 通用模板标签与过滤器
│
├── templates/                            # 全局 Django 模板
│   ├── base.html                         # 全局基础模板
│   │
│   ├── layouts/                          # 页面布局（仅前端；后台布局由三方主题库适配）
│   │   └── frontend.html                 # 前台页面布局
│   │
│   ├── includes/                         # 公共模板片段
│   │   ├── footer.html                   # 页面底部
│   │   ├── navbar.html                   # 导航栏
│   │   ├── pagination.html               # 分页组件
│   │   ├── messages.html                 # 消息提示
│   │   └── confirm_modal.html            # 通用确认弹窗
│   │
│   ├── registration/                     # Django 认证相关模板
│   │   └── password_reset_form.html      # 密码重置表单
│   │
│   └── errors/                           # 全局错误页面
│       ├── 403.html
│       ├── 404.html
│       └── 500.html
│
├── static/                               # 项目静态资源
│   ├── css/
│   │   ├── base.css                      # Tailwind v4 入口（@plugin "daisyui"），构建后引用 dist 产物
│   │   ├── frontend.css                  # 前台样式
│   │   └── dist/                         # Tailwind 构建产物（git 忽略）
│   │
│   ├── js/
│   │   ├── base.js                       # 全局 JavaScript
│   │   └── common.js                     # 通用交互逻辑
│   │
│   ├── images/                           # 项目静态图片
│   └── vendor/                           # 本地第三方静态资源（alpine.min.js / htmx.min.js）
│
├── media/                                # 用户上传文件目录
│   └── .gitkeep                         # 保留目录，不提交真实用户文件
│
├── database/                             # 数据库交付材料
│   ├── README.md                        # 数据库初始化与数据说明
│   │
│   ├── schema/                           # 数据库结构文件
│   │   ├── er-diagram.png                # ER 图
│   │   ├── er-diagram.drawio             # 可编辑 ER 图
│   │   └── schema.sql                    # 数据库结构 SQL
│   │
│   ├── data/                             # 数据库初始化与演示数据
│   │   ├── initial_data.json             # 基础初始化数据
│   │   └── demo_data.json                # 演示数据
│   │
│   └── backup/                           # 数据库备份（按需使用）
│       └── .gitkeep
│
├── docs/                                 # 面向客户的文档与论文材料
│   ├── README.md                         # 文档目录说明
│   │
│   ├── project/                          # 项目说明文档
│   │   ├── introduction.md               # 项目简介
│   │   ├── functional-description.md      # 功能说明（包含基础、核心、创新功能）
│   │   ├── technology-stack.md            # 技术栈说明
│   │   ├── system-architecture.md         # 系统架构说明
│   │   ├── seed-data-guide.md             # 种子数据填充指南（seedkit 统一 YAML）
│   │   └── seedkit-platform-integration.md # seedkit 中台接入说明（SSH 触发/轮询）
│   │
│   │
│   ├── deployment/                       # 部署文档
│   │   ├── local-deployment.md            # 本地部署说明
│   │   └── production-deployment.md       # 生产部署说明
│   │
│   ├── thesis/                           # 毕业论文材料
│   │   ├── README.md                     # 论文材料说明
│   │   ├── abstract.md                   # 摘要
│   │   ├── chapter-01-introduction.md    # 第一章：绪论
│   │   ├── chapter-02-related-technology.md
│   │   │                                  # 第二章：相关技术介绍
│   │   ├── chapter-03-system-analysis.md
│   │   │                                  # 第三章：需求分析
│   │   ├── chapter-04-system-design.md
│   │   │                                  # 第四章：系统设计
│   │   ├── chapter-05-system-implementation.md
│   │   │                                  # 第五章：系统实现
│   │   ├── chapter-06-system-testing.md
│   │   │                                  # 第六章：系统测试
│   │   ├── conclusion.md                 # 总结
│   │   ├── references.md                 # 参考文献
│   │   └── acknowledgements.md           # 致谢
│   │
│   ├── sop/                             # 团队内部 SOP（基座能力操作规范）
│   │   └── celery-async-tasks.md         # 异步任务与定时任务 SOP（Celery + Redis）
│   │
│   └── assets/                           # 文档与论文素材
│       ├── architecture/                 # 系统架构图
│       ├── database/                     # 数据库图
│       └── screenshots/                  # 系统截图
│
├── scripts/                              # 项目辅助脚本
│   ├── init_data.py                      # 基础数据初始化（超级用户等，make init-data）
│   ├── export_database.py                # 数据导出脚本（make export-db）
│   └── import_database.py                # 数据导入脚本（make import-db）
│
├── seeds/                                # seedkit 业务数据配置（统一 YAML 驱动）
│   ├── seed_data.yml                     # 所有模块数据的统一声明（modules → models → rows）
│   └── README.md                         # YAML Schema 速查（引用语法 / 图片 / 幂等）
│
├── deploy/                               # 部署配置
│   ├── Dockerfile                        # Docker 镜像构建文件（多阶段：前端构建 + 运行时）
│   ├── docker-compose.yml                # 容器编排（ACR 镜像 + 第三方数据库，静态由 WhiteNoise 提供）
│   └── entrypoint.sh                     # 容器启动脚本（迁移 / collectstatic / Gunicorn）
│
└── .github/
    └── workflows/
        └── deploy.yml                    # CI/CD：构建推送 ACR → 更新 compose → 部署健康检查
```
