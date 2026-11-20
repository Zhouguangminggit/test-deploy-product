# 种子数据填充指南

本地和线上共用 `seedkit_run` 与 `SEEDKIT_CONFIG`（默认 `seeds/seed_data.yml`）。提交 YAML 配置，并在运行环境设置 `PIXABAY_API_KEY`。脚本按业务关键词搜索图片、下载并写入 Django storage。默认生产 Compose 将 Web 与 Celery worker 的 `MEDIA_ROOT` 挂载到同一个卷。

## 每批交付

1. 逐个核对本批涉及的模型、字典、状态和业务流程，把所需的初始化和展示记录补进 `seeds/seed_data.yml` 或它引用的模块 YAML。只有结构化数据的模块也要补齐记录。纯基础设施或文档批次若无需调整种子，写明原因。
2. 单独判断资源需求。需要图片时，按本批模型的真实字段设置关键词来源，确保关键词符合主题与关联对象。无图片需求时省略 `images`。
3. 核对字段约束、业务键、关系目标和数据权限。配置至少应能通过 `load_config`。新关系或复杂规则在隔离测试库验证关联、重复执行和错误回滚，资源 API 用模拟响应。交付时列出已补模块和验证结果。实际环境的数据填充通过单独授权的初始化任务执行。

## 配置与关联

以校园二手交易为例，入口文件声明模块顺序。模块可直接写 `models`，也可以通过 `file` 拆分 YAML。

```yaml
# seeds/seed_data.yml
version: 2
modules:
  catalog: { file: catalog.yml }
  products: { file: products.yml }
```

```yaml
# seeds/catalog.yml
models:
  - model: catalog.Category
    match_by: slug
    rows:
      - { slug: electronics, name: 电子器材 }
```

```yaml
# seeds/products.yml
models:
  - model: products.Product
    match_by: code
    images:
      - field: cover
        keywords_from: title
    rows:
      - code: used-phone
        title: 二手手机
        category: { ref: "catalog.Category.electronics" }
  - model: products.ProductImage
    match_by: code
    images:
      - field: image
        keywords_from: product.title
    rows:
      - code: used-phone-detail
        product: { ref: "products.Product.used-phone" }
```

- `match_by` 对应模型的数据库唯一键，例如 `unique=True` 或由普通字段组成的 `UniqueConstraint`。可以写单个非关联字段或一组非关联字段。每行须提供非空键值。使用长期稳定的业务编码，避免使用会随环境变化的自增主键。
- `ref` 的格式为 `app_label.Model.键`。单字段匹配时默认使用该字段的值。行可用 `_key` 声明自定义引用键。组合键的行要被引用时，需声明 `_key`。被引用模型排在引用方之前。只运行商品模块时，分类须已经存在，系统仍会通过入口配置中的业务键查找它。
- 外键使用 `{ ref: "app.Model.key" }`，多对多使用 `{ refs: ["app.Model.key", …] }`。包含排序、说明等额外字段的中间表可作为独立模型声明。跨环境配置优先使用引用键。
- 模块 `file` 路径相对于入口 YAML 所在目录。文件必须存在且位于该目录内。

引擎从 Django 模型注册表和字段元数据解析配置。主题、模型名、字段名和关键词都由目标项目决定。当前通用入口按声明顺序处理依赖，`match_by` 支持有数据库唯一约束的非关联字段。依赖循环、以外键组成的匹配键，以及必须经业务 service 完成校验或副作用的场景，需由项目提供专用初始化入口。种子写入经 ORM，表单与 service 的领域规则需要通过业务测试验证。

## 按关键词补图

- 每个图片字段在模型的 `images` 配置中声明一次。`keywords_from: title` 取本行标题，`keywords_from: product.title` 沿外键取实际关联商品的标题。搜索词优先使用行内覆盖，例如 `cover: { keywords: "smartphone on desk" }`，其次使用字段值，最后使用模型配置中的固定 `keywords`。
- 一次运行内，相同关键词跨模型复用同一次检索并轮换候选图。候选图不足时可复用已用图片。检索结果缓存 24 小时，已下载图片按 Pixabay 图片 ID 缓存。详情见 [Pixabay API 文档](https://pixabay.com/api/docs/)。
- API 未配置、搜索无结果或网络和限流导致图片获取失败时，保留业务记录并在后台「数据初始化」记录警告。版本 2 重跑时会补齐空白图片字段，已有图片保持原值。图片关键词匹配用于演示，图片由搜索结果决定。

## 重复执行与失败

| 行为 | 版本 2 | 版本 1 |
| --- | --- | --- |
| 已有数据 | 按 `match_by` 复用已有记录，插入缺失行并补齐空白的关键词图片字段 | 表中已有记录时跳过该模型 |
| 失败范围 | 配置校验失败时不写业务数据。所选模块写入失败时全部回滚，并清理本次保存的文件 | 配置校验失败时不写业务数据。运行期每个模块独立回滚 |
| `--refresh` | 拒绝执行 | 保留逆序清空相关模型并重填的旧行为 |

版本 2 复用记录时会核对 YAML 显式配置的外键与多对多关系。关系与已有记录不一致时，报告对应模块、模型、行号和字段并回滚本次所选模块，已有关系保持原值。

旧项目可先为现有种子行补齐数据库唯一业务键和 `match_by`，确认配置与历史记录能正确匹配，再切换至版本 2。运行记录会保留新增、跳过、图片数量和异常明细。数据库唯一约束保护并发写入，发生冲突后可重新发起运行。同步命令的执行失败通过非零退出码报告。

## 本地与线上命令

```bash
# 本地，完成迁移后运行
make seed-data
uv run python manage.py seedkit_run --module products --sync
```

线上应用完成部署和迁移后，进入产品的部署根目录。中台会优先使用新版运行脚本，旧部署继续使用原有 Compose 命令。手工执行同步命令时，按[中台远程命令前置代码](../deployment/production-deployment.md#五中台触发部署及远程命令)定义 `compose`。

```bash
# 中台异步触发
sh deploy/product-runtime.sh seed-trigger

# 使用投递返回的 run_id 查询同一应用内的运行记录
sh deploy/product-runtime.sh seed-status "$RUN_ID"

# 需要同步执行时使用
compose exec -T web python manage.py seedkit_run --sync
```

中台先检查投递命令退出码，再从 stdout 的单行 JSON 取 `run_id`。查询返回 `pending` 或 `running` 时继续轮询，返回 `success`、`partial` 或 `failed` 时结束，并展示 `error` 与 `logs`。

纯 Web 产品使用临时容器，复用本次已部署的镜像和媒体卷。宿主机同一时刻只允许一个临时初始化任务，忙碌时可稍后重试。容器执行在 14 分钟内结束，查询会收尾异常退出的运行记录并清理已退出容器。启用了 Worker 的产品继续由 Celery 消费初始化任务。

`--module` 可重复传入。`seedkit_status` 支持 `--tail` 控制日志条数。后台「数据初始化」也可查看运行记录。基座的 `modules` 默认为空，业务项目按需声明自己的模型与素材。

## SimpleUI 模块统计

设置 `ADMIN_UI=simpleui` 后，`/admin/` 的 Home 标签打开「模块数据概览」。图表按后台应用分组汇总可见记录，明细显示各模型的记录数。新模型注册到 Django Admin 后会自动纳入统计。页面复用对应 `ModelAdmin` 的查看权限和 `get_queryset(request)`，新增行级权限时应在后台查询集里统一实现。运行 `make css` 会同时生成本地 ECharts 资源，生产镜像构建时会生成并由 Django 收集。
