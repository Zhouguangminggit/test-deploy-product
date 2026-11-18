"""seedkit.loader 校验测试（fail-fast，无需数据库）。

覆盖：合法配置解析、缺失文件/空 modules、未知模型/字段、反向关系、必填缺失、
非法 ref 格式、引用后声明模型、ref 目标与关联模型不一致、图片字段类型校验。
"""

import pytest
import yaml

from apps.seedkit.loader import SeedConfigError, load_config


def _dump(tmp_path, data):
    path = tmp_path / "seed_data.yml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _marketplace():
    return {
        "version": 1,
        "modules": {
            "products": {
                "models": [
                    {
                        "model": "seedkit.SeedCategory",
                        "rows": [{"name": "电子器材"}, {"name": "图书"}],
                    },
                    {
                        "model": "seedkit.SeedProduct",
                        "images": [{"field": "cover", "keywords_from": "title"}],
                        "rows": [
                            {"title": "手机", "category": {"ref": "seedkit.SeedCategory.电子器材"}},
                            {"title": "书籍", "category": {"ref": "seedkit.SeedCategory.图书"}},
                        ],
                    },
                ]
            }
        },
    }


def test_load_valid_config(tmp_path):
    config = load_config(_dump(tmp_path, _marketplace()))
    assert config.version == 1
    assert config.module_names() == ["products"]
    module = config.get_module("products")
    assert [m.label for m in module.models] == ["seedkit.SeedCategory", "seedkit.SeedProduct"]
    product = module.models[1]
    assert len(product.rows) == 2
    assert product.images[0].field == "cover"
    assert product.images[0].keywords_from == "title"
    # 声明顺序登记正确（分类在商品之前）
    assert module.models[0].order < module.models[1].order


def test_missing_file_returns_empty(tmp_path):
    config = load_config(tmp_path / "not-exists.yml")
    assert config.is_empty
    assert config.modules == []


def test_empty_modules_returns_empty(tmp_path):
    config = load_config(_dump(tmp_path, {"version": 1, "modules": {}}))
    assert config.is_empty


def test_unknown_model_raises(tmp_path):
    data = {"modules": {"m": {"models": [{"model": "seedkit.Nope", "rows": []}]}}}
    with pytest.raises(SeedConfigError, match="无法解析模型"):
        load_config(_dump(tmp_path, data))


def test_unknown_field_raises(tmp_path):
    data = {
        "modules": {"m": {"models": [{"model": "seedkit.SeedCategory", "rows": [{"bogus": 1}]}]}}
    }
    with pytest.raises(SeedConfigError, match="未知字段"):
        load_config(_dump(tmp_path, data))


def test_reverse_relation_field_raises(tmp_path):
    data = {
        "modules": {
            "m": {"models": [{"model": "seedkit.SeedCategory", "rows": [{"products": []}]}]}
        }
    }
    with pytest.raises(SeedConfigError, match="反向关系"):
        load_config(_dump(tmp_path, data))


def test_missing_required_field_raises(tmp_path):
    # SeedProduct 必填 title + category；缺 category 应报错
    data = {
        "modules": {
            "m": {
                "models": [
                    {"model": "seedkit.SeedCategory", "rows": [{"name": "电子器材"}]},
                    {"model": "seedkit.SeedProduct", "rows": [{"title": "手机"}]},
                ]
            }
        }
    }
    with pytest.raises(SeedConfigError, match="缺少必填字段"):
        load_config(_dump(tmp_path, data))


def test_ref_bad_format_raises(tmp_path):
    data = {
        "modules": {
            "m": {
                "models": [
                    {"model": "seedkit.SeedCategory", "rows": [{"name": "电子器材"}]},
                    {
                        "model": "seedkit.SeedProduct",
                        "rows": [{"title": "手机", "category": {"ref": "seedkit.SeedCategory"}}],
                    },
                ]
            }
        }
    }
    with pytest.raises(SeedConfigError, match="非法引用"):
        load_config(_dump(tmp_path, data))


def test_ref_forward_declaration_raises(tmp_path):
    # 商品先声明却引用后声明的分类 → 悬空引用
    data = {
        "modules": {
            "m": {
                "models": [
                    {
                        "model": "seedkit.SeedProduct",
                        "rows": [
                            {"title": "手机", "category": {"ref": "seedkit.SeedCategory.电子器材"}}
                        ],
                    },
                    {"model": "seedkit.SeedCategory", "rows": [{"name": "电子器材"}]},
                ]
            }
        }
    }
    with pytest.raises(SeedConfigError, match="后声明"):
        load_config(_dump(tmp_path, data))


def test_ref_target_model_mismatch_raises(tmp_path):
    # category 关联 SeedCategory，却 ref 到 SeedTag
    data = {
        "modules": {
            "m": {
                "models": [
                    {"model": "seedkit.SeedCategory", "rows": [{"name": "电子器材"}]},
                    {"model": "seedkit.SeedTag", "rows": [{"code": "数码"}]},
                    {
                        "model": "seedkit.SeedProduct",
                        "rows": [{"title": "手机", "category": {"ref": "seedkit.SeedTag.数码"}}],
                    },
                ]
            }
        }
    }
    with pytest.raises(SeedConfigError, match="关联模型"):
        load_config(_dump(tmp_path, data))


def test_image_field_must_be_filefield(tmp_path):
    data = {
        "modules": {
            "m": {
                "models": [
                    {
                        "model": "seedkit.SeedCategory",
                        "images": [{"field": "name"}],
                        "rows": [{"name": "电子器材"}],
                    }
                ]
            }
        }
    }
    with pytest.raises(SeedConfigError, match="不是图片/文件字段"):
        load_config(_dump(tmp_path, data))
