# 种子数据填充指南（seedkit）

> 业务系统所有模块的演示 / 初始化数据统一在 `seeds/seed_data.yml` 中**显式声明**，
> 本地 `make seed-data` 与线上中台触发（`seedkit_run`）加载同一份配置。
> 本文讲清 Schema、引用语法、图片规则、幂等与命令；速查见 `seeds/README.md`，
> 中台接入见 `docs/project/seedkit-platform-integration.md`。

## 一、设计原则

- **统一配置**：一个 YAML 描述所有业务模块数据，环境一致、可评审、可版本化；
- **显式声明**：逐行写明字段值，不使用随机造数（faker），保证内容真实可控；
- **关联真实**：行与行之间用 `ref` 引用，确保「手机 / 电脑挂电子器材、书籍挂图书」这类
  业务归属正确，图片关键词与行主题匹配；
- **fail-fast 校验**：任一模型 / 字段 / 引用非法，整体报错、**不落一条数据**；
- **可追溯**：每次运行一条 `SeedRun`，逐条过程日志 `SeedRunLog`，后台与 `seedkit_status` 可查。

## 二、快速开始

```bash
make seed-data                                  # 本地同步初始化（等价 seedkit_run --trigger local --sync）
uv run python manage.py seedkit_run --module products --sync   # 只跑某模块
uv run python manage.py seedkit_run --refresh --sync           # 强制重填
```

基座当前 `modules: {}` 为空，执行会输出「无可执行模块」并正常结束（非报错）。

## 三、配置结构

```yaml
version: 1
modules:
  <模块名>:                     # --module 过滤单位，一个业务主题一个模块
    models:
      - model: <app_label>.<ModelName>   # 必填
        images:                 # 选填，模型级图片字段配置
          - field: <图片字段名>
            keywords_from: <行内字段名>
            keywords: <固定回退关键词>
        rows:                   # 必填，逐行显式声明
          - <字段名>: <值>
            _key: <自定义被引用键>   # 选填
```

- 模型按 YAML **声明顺序**执行；被 `ref` 引用的模型**必须先声明**（loader 校验，杜绝悬空引用）。
- 顶层 `version` 目前固定为 `1`。

### 字段值类型

| 类型 | 写法 | 说明 |
| --- | --- | --- |
| 标量 | `name: 电子器材`、`price: 2999` | 直接赋值 |
| 日期 / 时间 | `released_at: 2024-05-01` | 按字段类型自动 `to_python` 转换（Date/DateTime/Time/Decimal） |
| 空值 | `desc: null` | 显式置空（字段需 `null=True`） |
| 外键 | `category: { ref: "products.Category.电子器材" }` 或 `category: 3` | `ref` 引用或直接给主键标量 |
| 多对多 | `tags: { refs: [ { ref: "products.Tag.数码" } ] }` 或 `tags: ["products.Tag.数码"]` | 列表内可混用 dict/字符串引用 |
| 图片行级覆盖 | `cover: { keywords: "book reading" }` | 覆盖该行的图片搜索关键词 |

## 四、引用语法（关联真实性核心）

`ref` 格式：`<app_label>.<Model>.<键>`。

- **键的取值**：缺省为目标模型**首个唯一非主键字段**的值（如 `Category.name`）；也可用主键数字；
  还可在目标行用 `_key: xxx` 自定义被引用键，引用处写 `ref: "app.Model.xxx"`。
- **解析顺序**：先查本次运行已创建对象的注册表，未命中回退查数据库
  （支持引用 `init-data` 等既有数据）。找不到即报错。
- **声明先后**：`ref` 只能指向**已声明**的模型；指向后声明模型会在加载期直接报错。

示例——手机 / 电脑 / 平板挂「电子器材」，书籍挂「图书」：

```yaml
- model: products.Product
  rows:
    - title: 手机
      category: { ref: "products.Category.电子器材" }
    - title: 书籍
      category: { ref: "products.Category.图书" }
```

## 五、图片配置（Pixabay）

对模型的 `ImageField / FileField`，在 `images` 中声明字段与关键词来源：

```yaml
images:
  - field: cover
    keywords_from: title      # 关键词取行内 title 的值（图文匹配）
    # keywords: "campus"      # 或该模型所有行共用的固定回退关键词
```

**关键词优先级**：行内 `{ keywords: "..." }` > 模型级 `keywords_from` > 模型级 `keywords`。

- 命中关键词后从 [Pixabay](https://pixabay.com/api/docs/) 检索下载，按图片 id 落盘缓存去重；
- 同字段多行按搜索结果**轮换分配不同图片**，避免全部同图；
- 图片存入 `MEDIA_ROOT`（容器已挂载卷），写入对应字段；
- **未配置 `PIXABAY_API_KEY` 时跳过图片下载**，仅填充结构化数据（不报错）。

## 六、幂等与 refresh

- **默认幂等**：某模型**已有数据则整体跳过**（记 `skipped`），只填充空模型，可安全重复执行；
- **`--refresh`**：按声明**逆序**（先子表后父表，规避外键约束）清空 YAML 声明模型的全部数据后重填。
  ⚠️ 会删除该模型所有行，线上使用前确认无需保留真实数据。

## 七、校验规则（加载期 fail-fast）

任一不满足即整体报错、不写库，错误信息含模块 / 模型 / 行号：

- `model` 必须能解析为已安装模型；`rows` 内键必须是模型真实字段（拒绝未知字段与反向关系）；
- **必填字段**（editable、非自增主键、无 default、非 null/blank）每行都要提供
  （由 `images` 负责填充的图片字段从必填集中剔除）；
- `ref` / `refs` 指向的模型须与关联模型一致，且不指向后声明模型；
- `images.field` 必须是 `FileField / ImageField`，`keywords_from` 必须是真实字段。

## 八、完整示例（分类 → 商品，含图片）

```yaml
version: 1
modules:
  products:
    models:
      - model: products.Category
        rows:
          - name: 电子器材
          - name: 图书
      - model: products.Product
        images:
          - field: cover
            keywords_from: title          # 封面图按商品标题检索，图文匹配
        rows:
          - title: 手机
            category: { ref: "products.Category.电子器材" }
            price: 2999
          - title: 电脑
            category: { ref: "products.Category.电子器材" }
            price: 5999
          - title: 书籍
            category: { ref: "products.Category.图书" }
            price: 59
            cover: { keywords: "book reading" }   # 行级覆盖：更精准的英文搜索词
```

执行后：手机 / 电脑归属「电子器材」、书籍归属「图书」，各自封面图按标题（书籍按覆盖词）检索。

## 九、命令与运行追溯

| 命令 | 用途 |
| --- | --- |
| `seedkit_run [--module X] [--refresh] [--trigger T] [--sync]` | 触发初始化；缺省异步投递 Celery，`--sync` 本地同步执行 |
| `seedkit_status [--run-id N] [--tail M]` | 查询运行状态、统计与日志（JSON） |

- 异步触发 stdout 输出 `{"run_id":…, "task_id":…, "status":"pending"}`，据此轮询 `seedkit_status`；
- 状态机：`pending → running → success / partial / failed`；`partial` 表示部分模块失败
  （失败模块已回滚，成功模块保留）；
- 运行记录与日志落库，Django 后台「数据初始化」菜单只读可查。

## 十、常见问题

| 现象 | 原因与处理 |
| --- | --- |
| 报「引用未找到」 | `ref` 的键在注册表与库中都无匹配；核对目标行是否声明、键值是否一致 |
| 报「引用了后声明的模型」 | 被引用模型写在了引用它的模型之后；调整声明顺序，父表在前 |
| 图片没下载 | 未配置 `PIXABAY_API_KEY`（会跳过图片）；或关键词无检索结果（日志有 warning） |
| 数据没变化 | 模型已有数据被幂等跳过；需重填加 `--refresh` |
| 报「缺少必填字段」 | 某行漏了 non-null 且无默认值的字段；按提示补齐 |
