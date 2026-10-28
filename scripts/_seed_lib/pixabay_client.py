"""Pixabay 图片资源 API 客户端。

基于 Pixabay 官方 API（https://pixabay.com/api/docs/）封装图片搜索与下载能力，
供种子数据填充时自动获取符合业务场景的图片资源。

核心特性：
- 关键词搜索图片，支持类型/方向/安全过滤
- 内置速率限制（100 req/60s），避免触发 Pixabay 限流
- 本地磁盘缓存，按关键词 hash 分目录存储，避免重复下载
"""

import hashlib
import time
from pathlib import Path

import requests
from loguru import logger


class PixabayClient:
    """Pixabay API 客户端。"""

    BASE_URL = "https://pixabay.com/api/"
    RATE_LIMIT = 90  # 保守值：60 秒内最多 90 次请求（官方上限 100）
    RATE_WINDOW = 60  # 速率窗口（秒）

    def __init__(self, api_key: str, cache_dir: Path) -> None:
        """初始化客户端。

        Args:
            api_key: Pixabay API 密钥（注册后在 https://pixabay.com/api/docs/ 获取）。
            cache_dir: 图片本地缓存根目录（如 media/seed_cache/）。
        """
        self.api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._request_timestamps: list[float] = []
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "django-scaffold-seed/1.0"})

    def _wait_for_rate_limit(self) -> None:
        """等待直到可以发送下一次请求（遵守速率限制）。"""
        now = time.time()
        # 移除窗口外的时间戳
        self._request_timestamps = [
            ts for ts in self._request_timestamps if now - ts < self.RATE_WINDOW
        ]
        if len(self._request_timestamps) >= self.RATE_LIMIT:
            oldest = self._request_timestamps[0]
            wait_time = self.RATE_WINDOW - (now - oldest) + 0.5
            if wait_time > 0:
                logger.debug("Pixabay 速率限制：等待 {:.1f}s", wait_time)
                time.sleep(wait_time)
        self._request_timestamps.append(time.time())

    @staticmethod
    def _keyword_hash(keyword: str) -> str:
        """关键词转短 hash（用于缓存目录名）。"""
        return hashlib.md5(keyword.encode()).hexdigest()[:12]

    def search(
        self,
        keyword: str,
        *,
        image_type: str = "photo",
        orientation: str = "all",
        per_page: int = 20,
        safesearch: bool = True,
        order: str = "popular",
    ) -> list[dict]:
        """搜索 Pixabay 图片，返回命中列表。

        Args:
            keyword: 搜索关键词（英文效果更好，如 "book"、"phone"）。
            image_type: 图片类型过滤（all/photo/illustration/vector）。
            orientation: 方向过滤（all/horizontal/vertical）。
            per_page: 每页返回数量（3-200）。
            safesearch: 是否启用安全搜索。
            order: 排序方式（popular/latest）。

        Returns:
            Pixabay hits 列表，每个元素包含 webformatURL、previewURL 等字段。
            搜索失败或无结果时返回空列表。
        """
        self._wait_for_rate_limit()

        params = {
            "key": self.api_key,
            "q": keyword,
            "lang": "zh",
            "image_type": image_type,
            "orientation": orientation,
            "per_page": per_page,
            "safesearch": str(safesearch).lower(),
            "order": order,
        }

        try:
            resp = self._session.get(self.BASE_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            hits = data.get("hits", [])
            logger.debug("Pixabay 搜索 '{}': 命中 {} 条", keyword, len(hits))
            return hits
        except requests.RequestException as exc:
            logger.warning("Pixabay 搜索失败 keyword='{}': {}", keyword, exc)
            return []

    def download_image(self, image_url: str, save_path: Path) -> Path | None:
        """下载单张图片到本地路径。

        Args:
            image_url: 图片 URL（Pixabay 返回的 webformatURL 或 largeImageURL）。
            save_path: 本地保存路径（含文件名）。

        Returns:
            保存成功的文件路径，失败返回 None。
        """
        self._wait_for_rate_limit()

        try:
            resp = self._session.get(image_url, timeout=30, stream=True)
            resp.raise_for_status()

            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.debug("图片已下载: {}", save_path)
            return save_path
        except requests.RequestException as exc:
            logger.warning("图片下载失败 url='{}': {}", image_url, exc)
            return None

    def fetch_and_cache(
        self,
        keyword: str,
        count: int = 1,
        *,
        image_type: str = "photo",
        orientation: str = "all",
    ) -> list[Path]:
        """搜索关键词并下载指定数量的图片到本地缓存。

        优先从本地缓存读取；缓存不足时才调用 API 补充下载。

        Args:
            keyword: 搜索关键词。
            count: 需要下载的图片数量。
            image_type: 图片类型过滤。
            orientation: 方向过滤。

        Returns:
            本地缓存图片路径列表（长度 <= count）。
        """
        kw_hash = self._keyword_hash(keyword)
        kw_cache_dir = self.cache_dir / kw_hash
        kw_cache_dir.mkdir(parents=True, exist_ok=True)

        # 检查已有缓存
        cached_files = sorted(kw_cache_dir.glob("*.jpg")) + sorted(kw_cache_dir.glob("*.png"))
        if len(cached_files) >= count:
            logger.debug("命中缓存 '{}': 已有 {} 张", keyword, len(cached_files))
            return cached_files[:count]

        # 缓存不足，调用 API 补充
        need = count - len(cached_files)
        hits = self.search(
            keyword,
            image_type=image_type,
            orientation=orientation,
            per_page=max(need * 2, 20),  # 多搜一些以备下载失败
        )

        downloaded = list(cached_files)
        for hit in hits:
            if len(downloaded) >= count:
                break

            image_url = hit.get("largeImageURL") or hit.get("webformatURL", "")
            if not image_url:
                continue

            # 用 Pixabay 图片 ID 作为文件名
            image_id = hit.get("id", "unknown")
            ext = "jpg"
            save_path = kw_cache_dir / f"{image_id}.{ext}"

            if save_path.exists():
                downloaded.append(save_path)
                continue

            result = self.download_image(image_url, save_path)
            if result:
                downloaded.append(result)

        logger.info("Pixabay '{}': 需要 {} 张，获取到 {} 张", keyword, count, len(downloaded))
        return downloaded[:count]

    def clear_cache(self, keyword: str | None = None) -> int:
        """清理本地缓存。

        Args:
            keyword: 指定关键词则只清理该关键词的缓存；为 None 则清理全部。

        Returns:
            删除的文件数量。
        """
        count = 0
        if keyword:
            kw_dir = self.cache_dir / self._keyword_hash(keyword)
            if kw_dir.exists():
                for f in kw_dir.iterdir():
                    f.unlink()
                    count += 1
                kw_dir.rmdir()
        else:
            for kw_dir in self.cache_dir.iterdir():
                if kw_dir.is_dir():
                    for f in kw_dir.iterdir():
                        f.unlink()
                        count += 1
                    kw_dir.rmdir()
        logger.info("缓存清理：删除 {} 个文件", count)
        return count
