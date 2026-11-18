import json
from io import StringIO
from pathlib import Path

import pytest
import yaml
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command
from PIL import Image

from apps.seedkit.loader import SeedConfigError, load_config
from apps.seedkit.services import execute_run_by_id
from utils import pixabay

from .testmodels import SeedCategory, SeedProduct, SeedProductImage


@pytest.fixture
def marketplace(tmp_path, settings, yaml_config):
    settings.MEDIA_ROOT = tmp_path / "media"
    Image.new("RGB", (4, 4), "red").save(tmp_path / "cover.png")
    Image.new("RGB", (4, 4), "blue").save(tmp_path / "content.png")
    products = {
        "models": [
            {
                "model": "seedkit.SeedProduct",
                "match_by": "title",
                "rows": [
                    {
                        "_key": "phone",
                        "title": "手机",
                        "category": {"ref": "seedkit.SeedCategory.electronics"},
                        "cover": {"asset": "phone-cover"},
                    }
                ],
            },
            {
                "model": "seedkit.SeedProductImage",
                "match_by": "code",
                "rows": [
                    {
                        "code": "phone-detail",
                        "product": {"ref": "seedkit.SeedProduct.phone"},
                        "image": {"asset": "phone-content"},
                    }
                ],
            },
        ]
    }
    (tmp_path / "products.yml").write_text(yaml.safe_dump(products), encoding="utf-8")
    return yaml_config(
        {
            "version": 2,
            "assets": {"phone-cover": "cover.png", "phone-content": "content.png"},
            "modules": {
                "categories": {
                    "models": [
                        {
                            "model": "seedkit.SeedCategory",
                            "match_by": "name",
                            "rows": [{"_key": "electronics", "name": "电子器材"}],
                        }
                    ]
                },
                "products": {"file": "products.yml"},
            },
        }
    )


@pytest.mark.django_db
def test_seed_command_reuses_rows_and_copies_exact_assets(marketplace, seedkit_tables):
    category = SeedCategory.objects.create(name="电子器材")
    other_category = SeedCategory.objects.create(name="线上已有分类")
    existing = SeedProduct.objects.create(title="线上已有商品", category=other_category)
    output = StringIO()
    call_command("seedkit_run", "--sync", "--module", "products", stdout=output)
    result = json.loads(output.getvalue())
    assert (result["created"], result["skipped"], result["images"]) == (2, 0, 2)
    product = SeedProduct.objects.get(category=category, title="手机")
    image = product.content_images.get(code="phone-detail").image
    for file, source in [(product.cover, "cover.png"), (image, "content.png")]:
        with file.open("rb") as stream:
            assert stream.read() == (marketplace.parent / source).read_bytes()

    output = StringIO()
    call_command("seedkit_run", "--sync", stdout=output)
    result = json.loads(output.getvalue())
    assert (result["created"], result["skipped"], result["images"]) == (0, 3, 0)
    assert SeedCategory.objects.count() == 2
    assert SeedProduct.objects.count() == 2
    assert SeedProduct.objects.get(pk=existing.pk).category_id == other_category.pk
    assert SeedProductImage.objects.count() == 1
    assert execute_run_by_id(result["run_id"]).skipped_count == 3
    assert len(list(marketplace.parent.joinpath("media").rglob("*.png"))) == 2


@pytest.mark.django_db
def test_bad_reference_rolls_back_all_selected_modules_and_files(
    marketplace, seedkit_tables, settings
):
    products = marketplace.parent / "products.yml"
    data = yaml.safe_load(products.read_text())
    data["models"][1]["rows"][0]["product"]["ref"] = "seedkit.SeedProduct.missing"
    products.write_text(yaml.safe_dump(data), encoding="utf-8")
    output = StringIO()

    with pytest.raises(CommandError):
        call_command("seedkit_run", "--sync", stdout=output)

    result = json.loads(output.getvalue())
    assert (result["status"], result["created"], result["images"]) == ("failed", 0, 0)
    assert "products/seedkit.SeedProductImage 第 1 行" in result["error"]
    assert "全部回滚" in result["error"]
    assert not SeedCategory.objects.exists()
    assert not SeedProduct.objects.exists()
    assert not list(Path(settings.MEDIA_ROOT).rglob("*.png"))


def test_asset_paths_cannot_escape_configuration_directory(marketplace):
    data = yaml.safe_load(marketplace.read_text())
    data["assets"]["phone-cover"] = "../cover.png"
    marketplace.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(SeedConfigError, match="文件不存在或超出配置目录"):
        load_config(marketplace)


@pytest.mark.django_db
def test_keyword_images_use_related_title_and_backfill_on_retry(
    marketplace, seedkit_tables, mock_pixabay, monkeypatch
):
    products = marketplace.parent / "products.yml"
    data = yaml.safe_load(products.read_text())
    product, content = data["models"]
    product["images"] = [{"field": "cover", "keywords_from": "title"}]
    content["images"] = [{"field": "image", "keywords_from": "product.title"}]
    del product["rows"][0]["cover"]
    del content["rows"][0]["image"]
    products.write_text(yaml.safe_dump(data), encoding="utf-8")

    with monkeypatch.context() as unavailable:

        def fail(_keyword):
            raise pixabay.PixabayError("Pixabay 检索失败（HTTP 429）")

        unavailable.setattr(pixabay, "search_images", fail)
        output = StringIO()
        call_command("seedkit_run", "--sync", stdout=output)
        result = json.loads(output.getvalue())
        assert (result["status"], result["created"], result["images"]) == ("success", 3, 0)
        run = execute_run_by_id(result["run_id"])
        assert run.logs.filter(message__contains="HTTP 429").count() == 2

    product = SeedProduct.objects.get(title="手机")
    assert not product.cover
    assert not product.content_images.get().image

    output = StringIO()
    call_command("seedkit_run", "--sync", stdout=output)
    result = json.loads(output.getvalue())
    assert (result["created"], result["skipped"], result["images"]) == (0, 3, 2)
    assert mock_pixabay.search_keywords == ["手机"]
    assert len(set(mock_pixabay.downloaded_ids)) == 2
    product.refresh_from_db()
    assert product.cover and product.content_images.get().image

    call_command("seedkit_run", "--sync", stdout=StringIO())
    assert mock_pixabay.search_keywords == ["手机"]


@pytest.mark.django_db
def test_account_and_group_seeds_support_other_fields_and_m2m(yaml_config, mock_pixabay):
    groups = [{"name": "场馆志愿者"}]
    account = {
        "username": "demo-volunteer",
        "password": make_password(None),
        "nickname": "场馆志愿者",
        "groups": {"refs": ["auth.Group.场馆志愿者"]},
    }
    data = {
        "version": 2,
        "modules": {
            "roles": {"models": [{"model": "auth.Group", "match_by": "name", "rows": groups}]},
            "profiles": {
                "models": [
                    {
                        "model": "accounts.User",
                        "match_by": "username",
                        "images": [{"field": "avatar", "keywords_from": "nickname"}],
                        "rows": [account],
                    }
                ]
            },
        },
    }
    yaml_config(data)
    call_command("seedkit_run", "--sync", stdout=StringIO())
    user = get_user_model().objects.get(username=account["username"])
    assert user.avatar and not user.has_usable_password()
    assert list(user.groups.values_list("name", flat=True)) == ["场馆志愿者"]
    assert mock_pixabay.search_keywords == ["场馆志愿者"]

    output = StringIO()
    call_command("seedkit_run", "--sync", stdout=output)
    result = json.loads(output.getvalue())
    assert (result["created"], result["skipped"], result["images"]) == (0, 2, 0)

    groups.append({"name": "场馆巡检员"})
    account["groups"]["refs"] = ["auth.Group.场馆巡检员"]
    yaml_config(data)
    output = StringIO()
    with pytest.raises(CommandError):
        call_command("seedkit_run", "--sync", stdout=output)
    assert "多对多字段 'groups' 与配置不一致" in json.loads(output.getvalue())["error"]
    assert not Group.objects.filter(name="场馆巡检员").exists()
    assert list(user.groups.values_list("name", flat=True)) == ["场馆志愿者"]


@pytest.mark.django_db
def test_existing_fk_conflict_keeps_record_and_rolls_back_other_modules(
    marketplace, seedkit_tables
):
    existing_category = SeedCategory.objects.create(name="线上已有分类")
    existing = SeedProduct.objects.create(title="手机", category=existing_category)

    output = StringIO()
    with pytest.raises(CommandError):
        call_command("seedkit_run", "--sync", stdout=output)

    assert "外键 'category' 与配置不一致" in json.loads(output.getvalue())["error"]
    assert not SeedCategory.objects.filter(name="电子器材").exists()
    existing.refresh_from_db()
    assert existing.category == existing_category
