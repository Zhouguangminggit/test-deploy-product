"""校园二手交易系统 —— 种子数据配置示例。

本文件演示如何为一个完整的业务主题系统编写种子配置。
注意：引用的模型（marketplace.*、forum.*）为假设的业务模型，
实际使用时需替换为项目中真实存在的模型路径。

业务模型结构（假设）：
    marketplace.Category    — 商品分类
    marketplace.Product     — 商品
    marketplace.Order       — 订单
    marketplace.Favorite    — 收藏
    forum.Board             — 论坛板块
    forum.Post              — 帖子
    forum.Comment           — 评论
    accounts.User           — 用户（基座已有）
    notifications.Message   — 消息（基座已有）
"""

MODULE = {
    "name": "demo_marketplace",
    "description": "校园二手交易系统（示例配置）",
    "dependencies": [],  # 无外部依赖，本模块自包含所有数据
    "models": [
        # ================================================================
        # 1. 用户（accounts.User）
        # ================================================================
        {
            "model": "accounts.User",
            "count": 20,
            "fields": {
                "username": {"type": "username", "prefix": "student"},
                "password": {"type": "password", "value": "test123456"},
                "email": {"type": "email"},
                "nickname": {"type": "name"},
                "phone": {"type": "phone"},
                "avatar": {
                    "type": "image",
                    "field": "avatar",
                    "keywords": ["student", "person", "face", "portrait", "people"],
                },
            },
        },
        # ================================================================
        # 2. 商品分类（marketplace.Category）
        # ================================================================
        {
            "model": "marketplace.Category",
            "count": 8,
            "fields": {
                "name": {
                    "type": "choice",
                    "choices": [
                        "数码电子",
                        "书籍教材",
                        "生活用品",
                        "服饰鞋包",
                        "运动户外",
                        "美妆护肤",
                        "票券卡类",
                        "其他",
                    ],
                },
                "description": {
                    "type": "text",
                    "pool": [
                        "各类数码产品和电子设备",
                        "教材、参考书、考试资料",
                        "宿舍生活用品",
                        "衣服、鞋子、包包",
                        "运动器材和户外装备",
                        "化妆品和护肤品",
                        "电影票、优惠券、会员卡",
                        "其他类别的二手物品",
                    ],
                },
                "sort_order": {"type": "int", "min": 0, "max": 100},
            },
        },
        # ================================================================
        # 3. 商品（marketplace.Product）
        # ================================================================
        {
            "model": "marketplace.Product",
            "count": 50,
            "fields": {
                "title": {
                    "type": "title",
                    "pool": [
                        "九成新 MacBook Pro 2024",
                        "考研英语全套资料",
                        "小米台灯 几乎全新",
                        "Nike 运动鞋 42码",
                        "罗技机械键盘",
                        "索尼 WH-1000XM5 耳机",
                        "大学物理教材 第三版",
                        "宜家收纳盒 三件套",
                        "Adidas 双肩包",
                        "iPad Air 5 256G",
                        "高等数学 同济第七版",
                        "飞利浦电动牙刷",
                        "Canon 单反相机",
                        "小米充电宝 20000mAh",
                        "全新未拆封 AirPods Pro",
                    ],
                },
                "description": {
                    "type": "text",
                    "pool": [
                        "使用不到半年，功能完好，无磕碰。因毕业低价出售，诚心出价可小刀。",
                        "买重了，全新未拆封，比书店便宜很多。适合考研和期末复习使用。",
                        "宿舍用了一学期，效果很好，搬家带不走，低价转让。",
                        "尺码买错了，只试穿过一次，吊牌还在。支持验货。",
                        "自用一年多，手感很好，换了新键盘所以出掉。配件齐全。",
                        "朋友送的，已经有一副了，这个全新转出。降噪效果一流。",
                        "课程结束了用不到了，书内有少量笔记，不影响使用。",
                        "质量很好，用了几个月想换个新的。可以面交验货。",
                    ],
                },
                "price": {"type": "float", "min": 5.0, "max": 5000.0, "precision": 2},
                "original_price": {"type": "float", "min": 50.0, "max": 10000.0, "precision": 2},
                "condition": {
                    "type": "choice",
                    "choices": ["全新", "几乎全新", "轻微使用痕迹", "明显使用痕迹"],
                },
                "status": {
                    "type": "choice",
                    "choices": ["on_sale", "on_sale", "on_sale", "sold", "off_shelf"],
                },
                "category": {
                    "type": "fk",
                    "ref": "marketplace.Category",
                    "strategy": "random",
                },
                "seller": {
                    "type": "fk",
                    "ref": "accounts.User",
                    "strategy": "random",
                },
                "cover_image": {
                    "type": "image",
                    "field": "cover_image",
                    "keywords": [
                        "laptop",
                        "book",
                        "shoes",
                        "headphones",
                        "phone",
                        "camera",
                        "keyboard",
                        "backpack",
                    ],
                },
                "created_at": {"type": "datetime", "days_back": 180},
                "view_count": {"type": "int", "min": 10, "max": 2000},
            },
        },
        # ================================================================
        # 4. 论坛板块（forum.Board）
        # ================================================================
        {
            "model": "forum.Board",
            "count": 5,
            "fields": {
                "name": {
                    "type": "choice",
                    "choices": [
                        "校园杂谈",
                        "学习互助",
                        "失物招领",
                        "兼职实习",
                        "二手交易",
                    ],
                },
                "description": {
                    "type": "text",
                    "pool": [
                        "畅聊校园生活，分享趣事见闻",
                        "课程答疑、学习资料分享、考试经验交流",
                        "捡到或丢失物品的发布信息",
                        "校内外兼职、实习、招聘信息",
                        "二手物品买卖、求购、交换",
                    ],
                },
                "icon": {
                    "type": "image",
                    "field": "icon",
                    "keywords": ["chat", "study", "search", "work", "trade"],
                },
            },
        },
        # ================================================================
        # 5. 帖子（forum.Post）
        # ================================================================
        {
            "model": "forum.Post",
            "count": 30,
            "fields": {
                "title": {
                    "type": "title",
                    "pool": [
                        "图书馆占座问题怎么解决？",
                        "求推荐好用的英语学习 APP",
                        "在食堂捡到一个校园卡",
                        "暑假实习经验分享——字节跳动",
                        "出一台闲置的 iPad",
                        "有没有人一起拼单外卖？",
                        "期末考试复习资料求分享",
                        "校园跑打卡互助",
                        "转让一张健身卡",
                        "求推荐性价比高的笔记本电脑",
                    ],
                },
                "content": {
                    "type": "text",
                    "pool": [
                        "如题，每天早上图书馆都是满座，大家有什么好的建议吗？",
                        "最近想学英语，之前用过多邻国但感觉进度太慢了，有没有更好的推荐？",
                        "今天下午在二食堂二楼捡到一个校园卡，卡号是 2024xxxx，请失主联系我。",
                        "刚结束字节的暑期实习，分享一下面试经验和实习感受，希望对学弟学妹有帮助。",
                        "毕业清理，出一台 iPad Air 5，256G，配 Apple Pencil，价格好商量。",
                        "有没有同学想一起点外卖的？满 30 减 15 的活动，人多更划算。",
                        "马上期末了，求分享高数和线代的复习资料，有偿也可以！",
                        "校园跑还差 10 次没打，有没有同学可以帮忙代跑的？有偿。",
                        "办了一张年卡，去了几次就不想去了，转让给有需要的同学。",
                        "预算 5000 左右，主要用来写代码和看论文，求推荐笔记本。",
                    ],
                },
                "author": {
                    "type": "fk",
                    "ref": "accounts.User",
                    "strategy": "random",
                },
                "board": {
                    "type": "fk",
                    "ref": "forum.Board",
                    "strategy": "round_robin",
                },
                "is_pinned": {"type": "bool", "true_rate": 0.1},
                "view_count": {"type": "int", "min": 5, "max": 500},
                "created_at": {"type": "datetime", "days_back": 90},
            },
        },
        # ================================================================
        # 6. 评论（forum.Comment）
        # ================================================================
        {
            "model": "forum.Comment",
            "count": 80,
            "fields": {
                "content": {
                    "type": "text",
                    "pool": [
                        "同感，我也遇到过类似的问题。",
                        "推荐试试 XXX，我用过效果不错。",
                        "可以私信我，我这里有资料。",
                        "谢谢分享！",
                        "这个价格可以，想要。",
                        "已联系卖家，交易成功。",
                        "顶一下，让更多人看到。",
                        "有没有更详细的介绍？",
                        "我也在找这个，终于看到了。",
                        "建议版主加精。",
                    ],
                },
                "author": {
                    "type": "fk",
                    "ref": "accounts.User",
                    "strategy": "random",
                },
                "post": {
                    "type": "fk",
                    "ref": "forum.Post",
                    "strategy": "random",
                },
                "created_at": {"type": "datetime", "days_back": 60},
            },
        },
        # ================================================================
        # 7. 订单（marketplace.Order）
        # ================================================================
        {
            "model": "marketplace.Order",
            "count": 15,
            "fields": {
                "product": {
                    "type": "fk",
                    "ref": "marketplace.Product",
                    "strategy": "specific",
                    "filter": {"status": "sold"},
                },
                "buyer": {
                    "type": "fk",
                    "ref": "accounts.User",
                    "strategy": "random",
                },
                "seller": {
                    "type": "fk",
                    "ref": "accounts.User",
                    "strategy": "random",
                },
                "status": {
                    "type": "choice",
                    "choices": ["completed", "completed", "pending", "cancelled"],
                },
                "created_at": {"type": "datetime", "days_back": 60},
            },
        },
        # ================================================================
        # 8. 收藏（marketplace.Favorite）
        # ================================================================
        {
            "model": "marketplace.Favorite",
            "count": 40,
            "fields": {
                "user": {
                    "type": "fk",
                    "ref": "accounts.User",
                    "strategy": "random",
                },
                "product": {
                    "type": "fk",
                    "ref": "marketplace.Product",
                    "strategy": "random",
                },
                "created_at": {"type": "datetime", "days_back": 90},
            },
        },
    ],
}
