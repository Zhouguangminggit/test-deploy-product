"""种子数据配置模板。

新业务模块接入步骤：
1. 复制本文件为 seeds/<module_name>.py
2. 修改 MODULE 字典中的各节配置
3. 执行 make seed 验证填充效果

═══════════════════════════════════════════════════════════════
字段类型（fields.<name>.type）
═══════════════════════════════════════════════════════════════
    auto       — 跳过，由 Django 自动处理（id, created_at 等）
    username   — 生成拼音用户名，可配 prefix
    name       — 生成中文姓名
    email      — 生成邮箱地址
    phone      — 生成手机号
    password   — 固定密码（默认 test123456）
    text       — 随机文本，可配 pool 列表
    title      — 随机标题，可配 pool 列表
    choice     — 从 choices 列表随机选取
    int        — 随机整数，可配 min / max
    float      — 随机浮点数，可配 min / max / precision
    datetime   — 随机时间，可配 days_back
    bool       — 随机布尔值，可配 true_rate
    fk         — 外键关联，需配 ref / strategy
    image      — Pixabay 图片，需配 field + (keywords 或 keywords_field)
    const      — 固定值，需配 value

═══════════════════════════════════════════════════════════════
外键策略（fk.strategy）
═══════════════════════════════════════════════════════════════
    random      — 随机选取一个已创建的目标对象
    round_robin — 轮询分配
    first       — 始终关联第一个
    specific    — 通过 filter 条件指定（需配 filter 字典）
    cycle       — 按实例索引轮询

═══════════════════════════════════════════════════════════════
模型配置模式
═══════════════════════════════════════════════════════════════
引擎支持两种模型配置模式：

1. generate 模式（默认）：按 fields 配置随机生成 count 条记录
   适用于：用户、日志等字段间无强关联的模型

2. rows 行模板模式：每行定义一条完整记录，字段间业务关联正确
   适用于：商品（标题+分类+图片关键词需匹配）、分类（名称+图标需对应）
   - 行内非 dict 值直接赋给模型字段（字符串外键自动解析为关联对象）
   - 行内 dict 值（含 type 键）作为字段配置覆盖 fields 中的同名配置
   - image 字段可用 keywords_field 引用行内的关键词列表
   - 非模型字段（如 pixabay_keywords）不会传给 Django ORM

═══════════════════════════════════════════════════════════════
图片后处理（post_process_images）
═══════════════════════════════════════════════════════════════
用于 generate 模式下子表图片需匹配父表主题的场景。
在所有记录创建完成后，按 FK 关联对象重新分配图片。

支持三种关键词解析策略（按优先级）：
  1. keywords_from_field — 从关联对象的指定字段读取关键词列表
  2. title_keyword_map   — 按关联对象的标题字段做模式匹配
  3. keywords            — 所有实例使用固定关键词（回退）
"""

MODULE = {
    # 模块唯一标识（也是 make seed-module MODULE=xxx 的参数值）
    "name": "my_module",
    # 模块描述（日志输出用）
    "description": "我的业务模块",
    # 依赖的其他模块 name（拓扑排序依据；被依赖的模块先执行）
    "dependencies": [],
    # 模型配置列表（按顺序执行，先创建的模型可被后续 fk 引用）
    "models": [
        # ────────────────────────────────────────────────────
        # 示例 1：generate 模式（字段间无强关联）
        # ────────────────────────────────────────────────────
        {
            "model": "app_label.ModelName",
            "count": 10,
            "fields": {
                # --- 文本字段 ---
                "name": {"type": "name"},
                "title": {
                    "type": "title",
                    "pool": ["标题A", "标题B", "标题C"],  # 可选：自定义标题池
                },
                "description": {
                    "type": "text",
                    "pool": ["描述文本1", "描述文本2"],  # 可选：自定义文本池
                },
                # --- 数值字段 ---
                "price": {"type": "float", "min": 9.9, "max": 999.9, "precision": 2},
                "stock": {"type": "int", "min": 0, "max": 100},
                # --- 选择/布尔字段 ---
                "status": {"type": "choice", "choices": ["draft", "published", "archived"]},
                "is_active": {"type": "bool", "true_rate": 0.8},
                # --- 外键字段 ---
                "author": {"type": "fk", "ref": "accounts.User", "strategy": "random"},
                "category": {"type": "fk", "ref": "my_module.Category", "strategy": "round_robin"},
                # --- 图片字段 ---
                "cover_image": {
                    "type": "image",
                    "field": "cover_image",  # 模型 ImageField 字段名
                    "keywords": ["book", "library", "reading"],  # Pixabay 搜索关键词
                },
            },
        },
        # ────────────────────────────────────────────────────
        # 示例 2：rows 行模板模式（字段间业务关联）
        # ────────────────────────────────────────────────────
        # {
        #     "model": "app_label.Item",
        #     "rows": [
        #         {
        #             "title": "具体标题",               # 直接赋值
        #             "category": "分类名",              # 字符串 → 自动解析为外键对象
        #             "pixabay_keywords": ["keyword1"],  # 非模型字段，供 image 引用
        #             "price": {"type": "float", "min": 10, "max": 100},  # 字段配置覆盖
        #             "cover": {
        #                 "type": "image",
        #                 "field": "cover",
        #                 "keywords_field": "pixabay_keywords",  # 引用行内关键词
        #             },
        #         },
        #         # ... 更多行
        #     ],
        #     "fields": {},  # 基础字段（与行内合并，行优先）
        # },
        # ────────────────────────────────────────────────────
        # 示例 3：图片后处理（子表图片匹配父表主题）
        # ────────────────────────────────────────────────────
        # {
        #     "model": "app_label.GalleryImage",
        #     "count": 30,
        #     "fields": {
        #         "item": {"type": "fk", "ref": "app_label.Item", "strategy": "cycle"},
        #         "image": {"type": "image", "field": "image", "keywords": ["default"]},
        #     },
        #     "post_process_images": {
        #         "fk_field": "item",                     # 外键字段名
        #         "title_field": "title",                  # 可选，默认自动检测 title/name
        #         "title_keyword_map": {                   # 策略 2：标题模式匹配
        #             "关键词A": ["pixabay_search_1"],
        #             "关键词B": ["pixabay_search_2"],
        #         },
        #         "keywords": ["fallback_keyword"],        # 策略 3：回退关键词
        #         "image_fields": ["image"],               # 需重新分配的图片字段
        #     },
        # },
    ],
}
