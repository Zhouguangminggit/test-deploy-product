"""Pixabay 免费图片资源客户端（utils 通用能力）。

seedkit 数据初始化时按关键词检索并下载场景图片，落到本地缓存目录。
API 文档：https://pixabay.com/api/docs/

约定与官方限制：
- 密钥取自 ``settings.PIXABAY_API_KEY``；留空时 ``search_images`` 返回空列表，
  由调用方（seedkit 引擎）跳过图片下载，仅填充结构化数据；
- 官方要求结果缓存 24h、限流 100 次/60s：下载结果按图片 id 落盘缓存
  （``settings.SEEDKIT_CACHE_DIR``），命中缓存不重复请求；
- 所有 HTTP 请求带 timeout；网络 / 鉴权 / 限流异常统一抛 ``PixabayError``
  并记 loguru 日志，不静默吞错。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import requests
from django.conf import settings
from loguru import logger

# 官方图片检索端点（GET）
PIXABAY_API_URL = "https://pixabay.com/api/"
# 单次请求超时（秒）：连接 + 读取
REQUEST_TIMEOUT = 15
# per_page 官方取值范围 3-200，默认 20 已够单模型多行分配
DEFAULT_PER_PAGE = 20
# 缓存图片统一存为 .jpg（webformatURL 返回 640px JPEG）
CACHE_SUFFIX = ".jpg"


class PixabayError(RuntimeError):
    """Pixabay 调用失败（网络、鉴权、限流、响应解析等）。"""


@dataclass(frozen=True)
class PixabayImage:
    """一条图片检索结果的轻量映射（仅保留 seedkit 需要的字段）。"""

    id: int
    page_url: str
    tags: str
    preview_url: str
    webformat_url: str
    large_image_url: str

    @classmethod
    def from_hit(cls, hit: dict) -> PixabayImage:
        """由官方 hits[] 元素构造；缺失字段回退空串/0，避免 KeyError。"""
        return cls(
            id=int(hit.get("id", 0)),
            page_url=hit.get("pageURL", ""),
            tags=hit.get("tags", ""),
            preview_url=hit.get("previewURL", ""),
            webformat_url=hit.get("webformatURL", ""),
            large_image_url=hit.get("largeImageURL", ""),
        )


def is_configured() -> bool:
    """是否已配置 Pixabay 密钥。"""
    return bool(getattr(settings, "PIXABAY_API_KEY", ""))


def _cache_dir(dest_dir: str | Path | None = None) -> Path:
    """解析图片缓存目录：显式传入优先，否则取 settings.SEEDKIT_CACHE_DIR。"""
    base = (
        dest_dir
        if dest_dir is not None
        else getattr(settings, "SEEDKIT_CACHE_DIR", "media/seed_cache")
    )
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def search_images(
    keyword: str,
    *,
    image_type: str = "photo",
    per_page: int = DEFAULT_PER_PAGE,
    page: int = 1,
    lang: str = "zh",
    min_width: int = 640,
    safe_search: bool = True,
    order: str = "popular",
) -> list[PixabayImage]:
    """按关键词检索图片，返回 ``PixabayImage`` 列表。

    - keyword 为空 → 返回空列表（不发起请求）；
    - 未配置密钥 → 记一次 warning 并返回空列表（调用方跳过图片）；
    - per_page 钳制到官方区间 [3, 200]；
    - HTTP / 网络异常 → 记日志并抛 ``PixabayError``。
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return []
    if not is_configured():
        logger.warning("PIXABAY_API_KEY 未配置，跳过图片检索：keyword={}", keyword)
        return []

    per_page = max(3, min(200, int(per_page)))
    params = {
        "key": settings.PIXABAY_API_KEY,
        "q": keyword,
        "image_type": image_type,
        "lang": lang,
        "per_page": per_page,
        "page": page,
        "min_width": min_width,
        "safesearch": "true" if safe_search else "false",
        "order": order,
    }
    try:
        resp = requests.get(PIXABAY_API_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:
        logger.error("Pixabay 检索失败：keyword={} err={}", keyword, exc)
        raise PixabayError(f"Pixabay 检索失败：{exc}") from exc
    except ValueError as exc:  # JSON 解析失败
        logger.error("Pixabay 响应解析失败：keyword={} err={}", keyword, exc)
        raise PixabayError(f"Pixabay 响应解析失败：{exc}") from exc

    hits = payload.get("hits", []) or []
    images = [PixabayImage.from_hit(hit) for hit in hits]
    logger.debug("Pixabay 检索：keyword={} 命中={}", keyword, len(images))
    return images


def download_image(image: PixabayImage, dest_dir: str | Path | None = None) -> Path | None:
    """下载单张图片到缓存目录，返回本地路径；命中缓存直接返回。

    无可用下载地址或下载失败时返回 None（调用方跳过该图，不中断整体填充）。
    """
    url = image.webformat_url or image.large_image_url or image.preview_url
    if not url or not image.id:
        return None

    target = _cache_dir(dest_dir) / f"{image.id}{CACHE_SUFFIX}"
    if target.exists() and target.stat().st_size > 0:
        return target

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, stream=True)
        resp.raise_for_status()
        with target.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    fh.write(chunk)
    except requests.RequestException as exc:
        logger.error("Pixabay 图片下载失败：id={} url={} err={}", image.id, url, exc)
        # 清理可能写坏的半成品文件，避免下次误命中缓存
        target.unlink(missing_ok=True)
        return None

    logger.debug("Pixabay 图片已缓存：id={} path={}", image.id, target)
    return target


def download_images_for_keyword(
    keyword: str,
    count: int = 1,
    dest_dir: str | Path | None = None,
    **search_kwargs,
) -> list[Path]:
    """检索关键词并下载最多 ``count`` 张不同图片，返回本地路径列表。

    seedkit 引擎按行分配图片时使用：同模型多行取搜索结果的前 N 张，
    避免所有行共用同一张图。结果可能少于 count（命中不足或部分下载失败）。
    """
    count = max(1, int(count))
    images = search_images(keyword, per_page=max(count, DEFAULT_PER_PAGE), **search_kwargs)
    if not images:
        return []

    paths: list[Path] = []
    for image in images:
        if len(paths) >= count:
            break
        local = download_image(image, dest_dir)
        if local is not None:
            paths.append(local)
    return paths
