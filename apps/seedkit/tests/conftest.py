"""seedkit 测试夹具。

- 导入 testmodels 即把临时模型注册到 seedkit app（managed=False，不产生迁移）；
- seedkit_tables：会话级用 schema_editor 临时建表 / 删表（引擎、服务、命令测试依赖）；
- yaml_config：把 dict 写成临时 YAML 并指向 settings.SEEDKIT_CONFIG，供 load_config 读取；
- FakeLog：记录 info/warning/error，替代 services.RunLogger 做无副作用断言。
"""

import pytest
import yaml
from django.db import connection

from utils.pixabay import PixabayImage

# 导入即把测试模型注册到 seedkit app registry（managed=False，不产生迁移）
from .testmodels import SeedCategory, SeedProduct, SeedTag


class FakeLog:
    """最小日志记录器，实现 engine.RunLog 协议。"""

    def __init__(self) -> None:
        self.records: list[tuple[str, str]] = []

    def info(self, message: str) -> None:
        self.records.append(("info", str(message)))

    def warning(self, message: str) -> None:
        self.records.append(("warning", str(message)))

    def error(self, message: str) -> None:
        self.records.append(("error", str(message)))

    def messages(self, level: str | None = None) -> list[str]:
        return [m for lv, m in self.records if level is None or lv == level]


@pytest.fixture(scope="session")
def seedkit_tables(django_db_setup, django_db_blocker):
    """会话级创建 / 销毁测试模型表（unmanaged 模型不在迁移中）。"""
    with django_db_blocker.unblock(), connection.schema_editor() as se:
        se.create_model(SeedCategory)
        se.create_model(SeedTag)
        se.create_model(SeedProduct)
    yield
    with django_db_blocker.unblock(), connection.schema_editor() as se:
        se.delete_model(SeedProduct)
        se.delete_model(SeedTag)
        se.delete_model(SeedCategory)


@pytest.fixture
def fake_log() -> FakeLog:
    return FakeLog()


@pytest.fixture
def yaml_config(tmp_path, settings):
    """写入临时 YAML 并把 settings.SEEDKIT_CONFIG 指向它，返回写文件的 callable。"""

    def _write(data: dict):
        path = tmp_path / "seed_data.yml"
        # sort_keys=False：保留模块/模型声明顺序（与手写 seed_data.yml 一致，ref 依赖声明先后）
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        settings.SEEDKIT_CONFIG = path
        return path

    return _write


class _PixabayRecorder:
    """记录 mock 后的 Pixabay 调用，供引擎测试断言关键词与分配到的图片。"""

    def __init__(self) -> None:
        self.search_keywords: list[str] = []
        self.downloaded_ids: list[int] = []


@pytest.fixture
def mock_pixabay(tmp_path, monkeypatch, settings):
    """把 pixabay 检索 / 下载换成可控替身，并隔离 MEDIA_ROOT。

    - search_images：同一关键词稳定返回 3 张不同 id 的图（验证多行按序轮换分配）；
    - download_image：返回真实存在的临时文件（写入少量字节），供引擎 File() 落盘；
    - MEDIA_ROOT 指向 tmp_path，避免测试图片写入仓库 media/。
    """
    settings.MEDIA_ROOT = str(tmp_path / "media")
    settings.PIXABAY_API_KEY = "test-key"

    rec = _PixabayRecorder()
    seen: dict[str, int] = {}

    def _fake_search(keyword, **kwargs):
        rec.search_keywords.append(keyword)
        if keyword not in seen:
            seen[keyword] = (len(seen) + 1) * 100
        base = seen[keyword]
        return [
            PixabayImage(
                id=base + i,
                page_url="",
                tags=keyword,
                preview_url="",
                webformat_url=f"https://example.test/{base + i}.jpg",
                large_image_url="",
            )
            for i in range(3)
        ]

    def _fake_download(image, dest_dir=None):
        rec.downloaded_ids.append(image.id)
        local = tmp_path / f"pix_{image.id}.jpg"
        if not local.exists():
            local.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01fakejpeg")
        return local

    monkeypatch.setattr("utils.pixabay.search_images", _fake_search)
    monkeypatch.setattr("utils.pixabay.download_image", _fake_download)
    return rec
