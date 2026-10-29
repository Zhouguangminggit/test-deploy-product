"""seedkit.engine 写库引擎测试（需数据库 + 临时表）。

覆盖方案核心诉求：
- ref 外键关联正确性（手机/电脑挂电子器材、书籍挂图书）；
- 多对多 refs、类型转换（Decimal/Date）、自定义 _key、显式 null 置空；
- 图片关键词优先级（行内覆盖 > keywords_from > 模型级固定）与多行轮换分配（Pixabay mock）；
- 幂等跳过、--refresh 逆序清空重填；
- ref 回退查库、模块级事务失败整体回滚（SeedRunPartial）、模块过滤与空选择。
"""

from datetime import date
from decimal import Decimal

import pytest
import yaml

from apps.seedkit.engine import SeedRunPartial, run_config
from apps.seedkit.loader import SeedConfigError, load_config

from .testmodels import SeedCategory, SeedProduct, SeedTag


def _load(tmp_path, data):
    """把 dict 写成临时 YAML 并经 loader 解析为 SeedConfig（保留声明顺序）。"""
    path = tmp_path / "seed.yml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return load_config(path)


def _marketplace(*, images=None, products=None):
    """分类（电子器材/图书）+ 商品两级 FK 的标准配置。"""
    category = {
        "model": "seedkit.SeedCategory",
        "rows": [{"name": "电子器材"}, {"name": "图书"}],
    }
    product = {
        "model": "seedkit.SeedProduct",
        "rows": products
        if products is not None
        else [
            {"title": "手机", "category": {"ref": "seedkit.SeedCategory.电子器材"}},
            {"title": "电脑", "category": {"ref": "seedkit.SeedCategory.电子器材"}},
            {"title": "书籍", "category": {"ref": "seedkit.SeedCategory.图书"}},
        ],
    }
    if images is not None:
        product["images"] = images
    return {"version": 1, "modules": {"products": {"models": [category, product]}}}


@pytest.mark.django_db
def test_ref_fk_association(tmp_path, seedkit_tables, fake_log):
    """关联真实性：手机/电脑挂电子器材、书籍挂图书。"""
    config = _load(tmp_path, _marketplace())
    stats = run_config(config, modules=None, refresh=False, log=fake_log)

    assert stats.created == 5  # 2 分类 + 3 商品
    elec = SeedCategory.objects.get(name="电子器材")
    book = SeedCategory.objects.get(name="图书")
    assert SeedProduct.objects.get(title="手机").category_id == elec.pk
    assert SeedProduct.objects.get(title="电脑").category_id == elec.pk
    assert SeedProduct.objects.get(title="书籍").category_id == book.pk
    # 反向核对：电子器材下恰为手机/电脑，图书下恰为书籍
    assert set(elec.products.values_list("title", flat=True)) == {"手机", "电脑"}
    assert set(book.products.values_list("title", flat=True)) == {"书籍"}


@pytest.mark.django_db
def test_custom_key_m2m_and_type_coercion(tmp_path, seedkit_tables, fake_log):
    """自定义 _key 引用、多对多 refs、Decimal/Date 转换、显式 null 置空。"""
    data = {
        "version": 1,
        "modules": {
            "products": {
                "models": [
                    {
                        "model": "seedkit.SeedCategory",
                        "rows": [{"_key": "elec", "name": "电子器材"}],
                    },
                    {"model": "seedkit.SeedTag", "rows": [{"code": "数码"}, {"code": "热销"}]},
                    {
                        "model": "seedkit.SeedProduct",
                        "rows": [
                            {
                                "title": "手机",
                                "category": {"ref": "seedkit.SeedCategory.elec"},
                                "price": "2999.00",
                                "released_at": "2024-05-01",
                                "tags": {
                                    "refs": [
                                        "seedkit.SeedTag.数码",
                                        "seedkit.SeedTag.热销",
                                    ]
                                },
                            },
                            {
                                "title": "样品",
                                "category": {"ref": "seedkit.SeedCategory.elec"},
                                "price": None,
                            },
                        ],
                    },
                ]
            }
        },
    }
    config = _load(tmp_path, data)
    run_config(config, modules=None, refresh=False, log=fake_log)

    phone = SeedProduct.objects.get(title="手机")
    assert phone.category.name == "电子器材"
    assert phone.price == Decimal("2999.00")
    assert phone.released_at == date(2024, 5, 1)
    assert set(phone.tags.values_list("code", flat=True)) == {"数码", "热销"}
    # 显式 null → 置空
    assert SeedProduct.objects.get(title="样品").price is None


@pytest.mark.django_db
def test_image_keyword_priority_and_rotation(tmp_path, seedkit_tables, fake_log, mock_pixabay):
    """行内 keywords 覆盖模型级 keywords_from；多行轮换分配不同图。"""
    data = _marketplace(
        images=[{"field": "cover", "keywords_from": "title"}],
        products=[
            {"title": "手机", "category": {"ref": "seedkit.SeedCategory.电子器材"}},
            {"title": "电脑", "category": {"ref": "seedkit.SeedCategory.电子器材"}},
            {
                "title": "书籍",
                "category": {"ref": "seedkit.SeedCategory.图书"},
                "cover": {"keywords": "book reading"},
            },
        ],
    )
    config = _load(tmp_path, data)
    stats = run_config(config, modules=None, refresh=False, log=fake_log)

    # 手机/电脑取 title，书籍被行内 keywords 覆盖
    assert mock_pixabay.search_keywords == ["手机", "电脑", "book reading"]
    assert stats.images == 3
    # cursor 轮换：三行分到互不相同的图片，避免全部同图
    assert len(set(mock_pixabay.downloaded_ids)) == 3
    for product in SeedProduct.objects.all():
        assert product.cover.name


@pytest.mark.django_db
def test_image_model_level_fixed_keyword(tmp_path, seedkit_tables, fake_log, mock_pixabay):
    """无行内覆盖时回退模型级固定 keywords；同关键词两行仍取不同图。"""
    data = _marketplace(
        images=[{"field": "cover", "keywords": "electronics"}],
        products=[
            {"title": "手机", "category": {"ref": "seedkit.SeedCategory.电子器材"}},
            {"title": "电脑", "category": {"ref": "seedkit.SeedCategory.电子器材"}},
        ],
    )
    config = _load(tmp_path, data)
    stats = run_config(config, modules=None, refresh=False, log=fake_log)

    assert mock_pixabay.search_keywords == ["electronics", "electronics"]
    assert len(set(mock_pixabay.downloaded_ids)) == 2
    assert stats.images == 2


@pytest.mark.django_db
def test_idempotent_skip(tmp_path, seedkit_tables, fake_log):
    """已有数据的模型再次执行 → 跳过，不重复写入。"""
    config = _load(tmp_path, _marketplace())
    first = run_config(config, modules=None, refresh=False, log=fake_log)
    assert (first.created, first.skipped) == (5, 0)

    second = run_config(config, modules=None, refresh=False, log=fake_log)
    assert (second.created, second.skipped) == (0, 5)
    assert SeedProduct.objects.count() == 3
    assert SeedCategory.objects.count() == 2
    assert any("跳过" in m for m in fake_log.messages("info"))


@pytest.mark.django_db
def test_refresh_clears_and_refills(tmp_path, seedkit_tables, fake_log):
    """--refresh：按声明逆序清空后重填，数量一致但主键全新。"""
    config = _load(tmp_path, _marketplace())
    run_config(config, modules=None, refresh=False, log=fake_log)
    old_ids = set(SeedProduct.objects.values_list("pk", flat=True))

    stats = run_config(config, modules=None, refresh=True, log=fake_log)
    assert stats.created == 5
    assert SeedCategory.objects.count() == 2
    assert SeedProduct.objects.count() == 3
    new_ids = set(SeedProduct.objects.values_list("pk", flat=True))
    assert new_ids.isdisjoint(old_ids)
    # 逆序删除日志：先清空商品（子表）再清空分类（父表）
    infos = fake_log.messages("info")
    assert any("refresh 清空 seedkit.SeedProduct" in m for m in infos)


@pytest.mark.django_db
def test_ref_resolves_from_existing_db(tmp_path, seedkit_tables, fake_log):
    """ref 未命中注册表时回退查库（模拟引用 init-data 既有数据）。"""
    SeedCategory.objects.create(name="电子器材")
    data = {
        "version": 1,
        "modules": {
            "products": {
                "models": [
                    {
                        "model": "seedkit.SeedProduct",
                        "rows": [
                            {
                                "title": "手机",
                                "category": {"ref": "seedkit.SeedCategory.电子器材"},
                            }
                        ],
                    }
                ]
            }
        },
    }
    config = _load(tmp_path, data)
    stats = run_config(config, modules=None, refresh=False, log=fake_log)

    assert stats.created == 1
    assert SeedProduct.objects.get(title="手机").category.name == "电子器材"
    assert SeedCategory.objects.count() == 1  # 未重复创建分类


@pytest.mark.django_db
def test_module_failure_rolls_back_whole_module(tmp_path, seedkit_tables, fake_log):
    """单模块内某行失败 → 整模块事务回滚，并以 SeedRunPartial 汇总。"""
    data = {
        "version": 1,
        "modules": {
            "products": {
                "models": [
                    {"model": "seedkit.SeedCategory", "rows": [{"name": "电子器材"}]},
                    {
                        "model": "seedkit.SeedProduct",
                        "rows": [
                            {
                                "title": "手机",
                                "category": {"ref": "seedkit.SeedCategory.不存在"},
                            }
                        ],
                    },
                ]
            }
        },
    }
    config = _load(tmp_path, data)
    with pytest.raises(SeedRunPartial) as exc:
        run_config(config, modules=None, refresh=False, log=fake_log)

    assert exc.value.failed_modules == ["products"]
    # 整模块回滚：先写入的分类也不残留
    assert SeedCategory.objects.count() == 0
    assert SeedProduct.objects.count() == 0
    assert any("回滚" in m for m in fake_log.messages("error"))


@pytest.mark.django_db
def test_run_config_module_filter(tmp_path, seedkit_tables, fake_log):
    """--module 过滤：只执行选中模块，其余不写入。"""
    data = {
        "version": 1,
        "modules": {
            "cats": {
                "models": [
                    {"model": "seedkit.SeedCategory", "rows": [{"name": "电子器材"}]},
                ]
            },
            "tags": {"models": [{"model": "seedkit.SeedTag", "rows": [{"code": "数码"}]}]},
        },
    }
    config = _load(tmp_path, data)
    stats = run_config(config, modules=["cats"], refresh=False, log=fake_log)

    assert stats.created == 1
    assert SeedCategory.objects.count() == 1
    assert SeedTag.objects.count() == 0


def test_run_config_unknown_module_raises(tmp_path, fake_log):
    """指定了 YAML 中不存在的模块 → 直接报错（无需数据库）。"""
    config = _load(tmp_path, _marketplace())
    with pytest.raises(SeedConfigError, match="不存在"):
        run_config(config, modules=["ghost"], refresh=False, log=fake_log)


def test_run_config_empty_selection_warns(tmp_path, fake_log):
    """无声明模块 → 记 warning「无可执行模块」并返回零统计，而非报错。"""
    config = _load(tmp_path, {"version": 1, "modules": {}})
    stats = run_config(config, modules=None, refresh=False, log=fake_log)

    assert (stats.created, stats.skipped, stats.images) == (0, 0, 0)
    assert any("无可执行模块" in m for m in fake_log.messages("warning"))
