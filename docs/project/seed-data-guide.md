# 种子数据填充指南

> 业务模块开发完成后，通过种子数据一键填充真实业务数据和场景图片。

## 前置条件

1. 在 [Pixabay](https://pixabay.com/api/docs/) 注册免费账号，获取 API Key
2. 在 `.env` 中配置 `PIXABAY_API_KEY=你的密钥`
3. 确保业务模块的模型和迁移已就绪（`make migrate`）

## 快速开始

```bash
# 查看所有可用种子模块
make seed-list

# 填充所有模块（含图片下载）
make seed

# 填充所有模块（跳过图片，开发调试推荐）
make seed-no-images

# 只填充指定模块
make seed-module MODULE=my_module

# 预览模式（不实际写入）
uv run python scripts/seed_data.py --dry-run
```

## 新增业务模块种子配置（3 步）

### 第一步：复制模板

```bash
cp seeds/_template.py seeds/my_module.py
```

### 第二步：编辑配置

打开 `seeds/my_module.py`，按模板注释填写：

```python
MODULE = {
    "name": "my_module",  # 模块唯一标识
    "description": "模块描述",
    "dependencies": [],  # 依赖的其他模块（拓扑排序）
    "models": [
        {
            "model": "app_label.ModelName",  # Django 模型路径
            "count": 10,  # 生成记录数
            "fields": {
                "title": {"type": "title", "pool": ["标题1", "标题2"]},
                "price": {"type": "float", "min": 9.9, "max": 999.9},
                "author": {"type": "fk", "ref": "accounts.User", "strategy": "random"},
                "cover": {"type": "image", "field": "cover", "keywords": ["book", "reading"]},
            },
        },
    ],
}
```

### 第三步：执行填充

```bash
make seed
```

## 字段类型速查

| type | 说明 | 常用参数 |
|------|------|----------|
| `username` | 拼音用户名 | `prefix` |
| `name` | 中文姓名 | - |
| `email` | 邮箱地址 | - |
| `phone` | 手机号 | - |
| `password` | 固定密码 | `value`（默认 test123456） |
| `text` | 随机文本 | `pool`（自定义文本池） |
| `title` | 随机标题 | `pool`（自定义标题池） |
| `choice` | 从列表选取 | `choices` |
| `int` | 随机整数 | `min`, `max` |
| `float` | 随机浮点数 | `min`, `max`, `precision` |
| `datetime` | 随机时间 | `days_back` |
| `bool` | 随机布尔值 | `true_rate` |
| `fk` | 外键关联 | `ref`, `strategy` |
| `image` | Pixabay 图片 | `field`, `keywords` 或 `keywords_field` |
| `const` | 固定值 | `value` |

## 行模板模式（rows）

当同一记录的多个字段需要业务关联时（如商品标题与分类匹配、图片关键词与商品对应），使用 `rows` 代替 `count`：

```python
{
    "model": "products.Product",
    "rows": [
        {
            "title": "iPhone 15 Pro",  # 直接赋值
            "category": "数码电子",  # 字符串自动解析为外键
            "pixabay_keywords": ["smartphone"],  # 非模型字段，供图片引用
            "price": {"type": "float", "min": 5999, "max": 7999},  # 字段配置覆盖
            "cover_image": {
                "type": "image",
                "field": "cover_image",
                "keywords_field": "pixabay_keywords",
            },
        },
        # ... 更多行
    ],
    "fields": {},  # 基础字段配置（与行内合并，行优先）
}
```

**规则**：

- 行内非 dict 值直接赋给模型字段（字符串外键自动解析为关联对象）
- 行内 dict 值（含 `type`）作为字段配置覆盖 `fields` 中的同名配置
- `keywords_field` 让图片字段引用行内的关键词列表，实现图片与商品主题匹配
- 行内非模型字段（如 `pixabay_keywords`）不会传给 Django ORM

## 图片后处理（post_process_images）

用于 generate 模式下子表图片需匹配父表主题的场景。在所有记录创建完成后，按 FK 关联对象重新分配图片。

支持三种关键词解析策略（按优先级）：

| 策略 | 配置键 | 适用场景 |
|------|--------|----------|
| 字段读取 | `keywords_from_field` | 关联模型本身存储了关键词（如 Article.tags） |
| 标题匹配 | `title_keyword_map` | 标题与图片主题存在明确映射（如商品名 → 搜索词） |
| 固定回退 | `keywords` | 所有实例共享同一主题（如公司 Logo） |

```python
{
    "model": "app_label.GalleryImage",
    "count": 30,
    "fields": {
        "item": {"type": "fk", "ref": "app_label.Item", "strategy": "cycle"},
        "image": {"type": "image", "field": "image", "keywords": ["default"]},
    },
    "post_process_images": {
        "fk_field": "item",  # 外键字段名
        "title_field": "title",  # 可选，默认自动检测 title/name
        "title_keyword_map": {  # 策略 2：标题模式匹配
            "关键词A": ["pixabay_search_1"],
            "关键词B": ["pixabay_search_2"],
        },
        "keywords": ["fallback_keyword"],  # 策略 3：回退关键词
        "image_fields": ["image"],  # 需重新分配的图片字段
    },
}
```

## 外键关联策略

| strategy | 说明 |
|----------|------|
| `random` | 随机选取一个已创建的目标对象 |
| `round_robin` | 轮询分配（均匀分布） |
| `first` | 始终关联第一个 |
| `cycle` | 按实例索引轮询 |
| `specific` | 通过 `filter` 条件指定 |

## 生产部署

部署到线上服务器后，一键填充数据：

```bash
# 确保服务器 .env 中配置了 PIXABAY_API_KEY
make seed-prod
```

图片下载到服务器 `media/seed_cache/`，数据写入生产数据库。

建议首次部署执行顺序：

```bash
make migrate && make init-data && make seed-prod
```

## 注意事项

- 图片缓存位于 `media/seed_cache/`，同一关键词只下载一次，后续复用
- Pixabay API 限制 100 次/分钟，引擎内置自动节流，大量图片时请耐心等待
- 配置中未声明的字段使用模型默认值或留空
- User 模型自动使用 `create_user` 创建（密码正确哈希）
- 单模块填充失败不影响其他模块（独立事务）
