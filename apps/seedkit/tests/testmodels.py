"""seedkit 引擎测试专用的临时模型（不入库迁移）。

以 ``managed = False`` 注册到 seedkit app：迁移自动探测器会跳过它们，
表结构由 conftest 的 schema_editor 在测试期临时创建 / 销毁，用于验证
ref 关联、图片分配、幂等与 refresh 等引擎行为，无需引入真实业务模型。

模型刻意模拟「分类 → 商品」两级外键 + 图片 + 多对多 + 日期/金额字段，
覆盖方案中「手机/电脑挂电子器材、书籍挂图书且图文匹配」的核心诉求。
"""

from django.db import models


class SeedCategory(models.Model):
    """分类（唯一 name，作为被 ref 的自然键）。"""

    name = models.CharField(max_length=50, unique=True)

    class Meta:
        app_label = "seedkit"
        managed = False


class SeedTag(models.Model):
    """标签（用于多对多引用测试）。"""

    code = models.CharField(max_length=20, unique=True)

    class Meta:
        app_label = "seedkit"
        managed = False


class SeedProduct(models.Model):
    """商品：外键挂分类、图片封面、多对多标签、金额与日期字段（类型转换）。"""

    title = models.CharField(max_length=100)
    category = models.ForeignKey(SeedCategory, on_delete=models.CASCADE, related_name="products")
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    released_at = models.DateField(null=True, blank=True)
    cover = models.ImageField(upload_to="seedkit_test/", blank=True)
    tags = models.ManyToManyField(SeedTag, blank=True, related_name="products")

    class Meta:
        app_label = "seedkit"
        managed = False
