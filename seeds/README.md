# 种子配置

`seed_data.yml` 是本地与线上共用的配置入口。版本 2 按唯一业务键补齐数据。配置 `PIXABAY_API_KEY` 后，在模型的 `images` 中用 `keywords_from` 指定搜索词来源。商品封面可取 `title`，内容图可取关联商品的 `product.title`。

分类、商品与内容图的完整示例、旧版配置迁移及线上执行命令见[种子数据填充指南](../docs/project/seed-data-guide.md)。
