"""utils.pixabay 客户端测试。

覆盖：检索成功 / 未配置密钥跳过 / 空关键词 / HTTP 异常抛错 / per_page 钳制、
图片下载落盘缓存与命中缓存不重复请求、按关键词下载多张不同图片。
所有网络请求均以 monkeypatch 替换 requests.get，不触达真实 Pixabay。
"""

import pytest
import requests

from utils import pixabay
from utils.pixabay import PixabayError, PixabayImage


class _FakeResponse:
    """最小可用的 requests.Response 替身。"""

    def __init__(self, *, payload=None, chunks=None, status_ok=True):
        self._payload = payload or {}
        self._chunks = chunks or []
        self._status_ok = status_ok

    def raise_for_status(self):
        if not self._status_ok:
            raise requests.HTTPError("429 Too Many Requests")

    def json(self):
        return self._payload

    def iter_content(self, chunk_size=8192):  # noqa: ANN001
        yield from self._chunks


def _hits(*ids):
    return {
        "total": len(ids),
        "totalHits": len(ids),
        "hits": [
            {
                "id": i,
                "pageURL": f"https://pixabay.com/p/{i}/",
                "tags": "phone, gadget",
                "previewURL": f"https://cdn/{i}_150.jpg",
                "webformatURL": f"https://cdn/{i}_640.jpg",
                "largeImageURL": f"https://cdn/{i}_1280.jpg",
            }
            for i in ids
        ],
    }


@pytest.fixture
def api_key(settings, tmp_path):
    settings.PIXABAY_API_KEY = "test-key"
    settings.SEEDKIT_CACHE_DIR = tmp_path / "pixabay"
    return "test-key"


def test_search_images_success(api_key, monkeypatch):
    captured = {}

    def _fake_get(url, params=None, **kwargs):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse(payload=_hits(101, 102))

    monkeypatch.setattr(pixabay.requests, "get", _fake_get)
    images = pixabay.search_images("手机")

    assert [img.id for img in images] == [101, 102]
    assert isinstance(images[0], PixabayImage)
    assert images[0].webformat_url == "https://cdn/101_640.jpg"
    # 关键参数按官方约定拼装
    assert captured["url"] == pixabay.PIXABAY_API_URL
    assert captured["params"]["key"] == "test-key"
    assert captured["params"]["q"] == "手机"
    assert captured["params"]["safesearch"] == "true"
    monkeypatch.setattr(
        pixabay.requests, "get", lambda *a, **k: pytest.fail("相同搜索应复用本地缓存")
    )
    assert pixabay.search_images("手机") == images


def test_search_images_skips_without_key(settings, monkeypatch):
    settings.PIXABAY_API_KEY = ""
    called = {"n": 0}

    def _fake_get(*args, **kwargs):
        called["n"] += 1
        return _FakeResponse(payload=_hits(1))

    monkeypatch.setattr(pixabay.requests, "get", _fake_get)
    assert pixabay.search_images("手机") == []
    assert called["n"] == 0  # 未配置密钥不发起请求


def test_search_images_empty_keyword(api_key, monkeypatch):
    monkeypatch.setattr(
        pixabay.requests, "get", lambda *a, **k: pytest.fail("空关键词不应发起请求")
    )
    assert pixabay.search_images("   ") == []


def test_search_images_per_page_clamped(api_key, monkeypatch):
    captured = {}

    def _fake_get(url, params=None, **kwargs):
        captured["params"] = params
        return _FakeResponse(payload=_hits(1))

    monkeypatch.setattr(pixabay.requests, "get", _fake_get)
    pixabay.search_images("book", per_page=9999)
    assert captured["params"]["per_page"] == 200  # 钳制到官方上限


def test_search_images_http_error_raises(api_key, monkeypatch):
    def fail(*args, **kwargs):
        raise requests.ConnectionError("https://pixabay.com/api/?key=test-key")

    monkeypatch.setattr(pixabay.requests, "get", fail)
    with pytest.raises(PixabayError, match=r"^Pixabay 检索失败（ConnectionError）$"):
        pixabay.search_images("手机")


def test_download_image_caches_and_reuses(api_key, monkeypatch, tmp_path):
    calls = {"n": 0}

    def _fake_get(url, **kwargs):
        calls["n"] += 1
        return _FakeResponse(chunks=[b"\xff\xd8", b"imgdata"])

    monkeypatch.setattr(pixabay.requests, "get", _fake_get)
    image = PixabayImage.from_hit(_hits(55)["hits"][0])

    first = pixabay.download_image(image, tmp_path)
    assert first is not None and first.exists() and first.name == "55.jpg"
    assert first.read_bytes() == b"\xff\xd8imgdata"

    second = pixabay.download_image(image, tmp_path)
    assert second == first
    assert calls["n"] == 1  # 命中缓存，不再下载


def test_download_images_for_keyword_distinct(api_key, monkeypatch, tmp_path):
    def _fake_get(url, params=None, **kwargs):
        if url == pixabay.PIXABAY_API_URL:
            return _FakeResponse(payload=_hits(11, 12, 13))
        return _FakeResponse(chunks=[b"data"])

    monkeypatch.setattr(pixabay.requests, "get", _fake_get)
    paths = pixabay.download_images_for_keyword("电脑", count=2, dest_dir=tmp_path)
    assert len(paths) == 2
    assert {p.name for p in paths} == {"11.jpg", "12.jpg"}


def test_download_images_for_keyword_no_key(settings, monkeypatch, tmp_path):
    settings.PIXABAY_API_KEY = ""
    monkeypatch.setattr(
        pixabay.requests, "get", lambda *a, **k: pytest.fail("未配置密钥不应发起请求")
    )
    assert pixabay.download_images_for_keyword("电脑", count=3, dest_dir=tmp_path) == []
