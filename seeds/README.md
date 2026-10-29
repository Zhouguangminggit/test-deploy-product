# seeds 配置速查（seedkit）

`seed_data.yml` 是业务系统所有模块数据的**统一声明文件**。本地 `make seed-data`
与线上中台触发（`seedkit_run`）加载同一份配置，保证环境一致。

## 顶层结构

```yaml
version: 1
modules:
  <模块名>:            # --module 过滤单位，一个业务主题一个模块
    models:
      - model: <app_label>.<ModelName>
        images: [...]  # 选填
        rows: [...]    # 必填，逐行显式声明
```

- 模型按 YAML **声明顺序**执行，被引用模型必须先声明（loader 会校验，杜绝悬空引用）。
- 数据全部**显式声明**，不使用随机造数，保证关联与内容真实、可评审。

## 引用语法（保证关联真实性）

| 关系 | 写法 |
| --- | --- |
| 外键 | `category: { ref: "products.Category.电子器材" }` |
| 外键（直接给主键） | `category: 3` |
| 多对多 | `tags: { refs: [ { ref: "products.Tag.数码" } ] }` 或 `tags: ["products.Tag.数码"]` |
| 自定义被引用键 | 目标行加 `_key: xxx`，引用处写 `ref: "app.Model.xxx"` |

- `ref` 格式为 `<app_label>.<Model>.<键>`；键缺省取目标模型**首个唯一字段**的值
  （如 Category.name），未命中运行注册表时回退查库（支持引用 init-data 等既有数据）。
- 示例：手机 / 电脑 / 平板 `ref` 到「电子器材」，书籍 `ref` 到「图书」，即保证分类归属正确。

## 图片关键词优先级

针对模型的 `ImageField / FileField`，在 `images` 中声明字段与关键词来源：

```yaml
images:
  - field: cover
    keywords_from: title      # 关键词取行内 title（图文匹配）
    # keywords: "campus"      # 或固定回退关键词
```

优先级：**行内 `{ keywords: "..." }` > 模型级 `keywords_from` > 模型级 `keywords`**。
关键词命中后从 Pixabay 检索下载（按 id 缓存去重），同字段多行轮换分配不同图片。
未配置 `PIXABAY_API_KEY` 时跳过图片下载，仅填充结构化数据。

## 幂等与 refresh

- 默认：模型**已有数据则跳过**（记 skipped），只填充空模型，安全可重复执行。
- `--refresh`：按声明**逆序**（先子表后父表，规避外键约束）清空 YAML 声明的模型后重填。
  会删除该模型全部数据，请确认无需保留线上真实数据再使用。

## 常用命令

```bash
make seed-data                                   # 本地同步初始化全部模块
uv run python manage.py seedkit_run --sync       # 等价（可加 --module / --refresh）
uv run python manage.py seedkit_run              # 线上：异步投递 Celery，输出 run_id JSON
uv run python manage.py seedkit_status --run-id <id>   # 查询进度与日志（JSON）
```

运行记录与逐条日志落库（后台「数据初始化」可查），中台接入详见
`docs/project/seedkit-platform-integration.md`。
