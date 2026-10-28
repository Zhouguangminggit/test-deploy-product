"""图片资源获取工具 —— 将 Pixabay 下载的图片集成到 Django 文件体系。

提供两个层面的能力：
1. ``get_cached_image_path``：从 Pixabay 缓存获取图片本地路径（供种子引擎直接赋值给 ImageField）
2. ``fetch_seed_image``：下载图片并创建 FileEntry 记录（供需要文件管理记录的场景使用）

种子数据填充时通常使用 ``get_cached_image_path``，直接将图片路径赋给模型的 ImageField。
"""

import uuid
from pathlib import Path

from django.conf import settings
from django.core.files import File
from loguru import logger


def _get_pixabay_client():
    """延迟导入并构造 PixabayClient（避免脚本外导入时 Django 未就绪）。"""
    from scripts._seed_lib.pixabay_client import PixabayClient

    api_key = getattr(settings, "PIXABAY_API_KEY", "")
    cache_dir = getattr(settings, "SEED_CACHE_DIR", settings.BASE_DIR / "media/seed_cache")
    if not api_key:
        return None
    return PixabayClient(api_key=api_key, cache_dir=Path(cache_dir))


def get_cached_image_path(
    keyword: str,
    *,
    index: int = 0,
    image_type: str = "photo",
    orientation: str = "all",
) -> Path | None:
    """从 Pixabay 获取一张缓存图片的本地路径。

    Args:
        keyword: 搜索关键词（英文效果更佳，如 "book"、"laptop"）。
        index: 取第几张（0 表示第一张），用于同一关键词获取不同图片。
        image_type: 图片类型过滤。
        orientation: 方向过滤。

    Returns:
        本地图片绝对路径；API 密钥未配置或下载失败时返回 None。
    """
    client = _get_pixabay_client()
    if client is None:
        logger.warning("PIXABAY_API_KEY 未配置，跳过图片下载 keyword='{}'", keyword)
        return None

    images = client.fetch_and_cache(
        keyword, count=index + 1, image_type=image_type, orientation=orientation
    )
    if index < len(images):
        return images[index]
    logger.warning("Pixabay '{}' 仅获取到 {}/{} 张图片", keyword, len(images), index + 1)
    return images[-1] if images else None


def assign_image_to_field(instance, field_name: str, image_path: Path) -> bool:
    """将本地图片赋值给模型实例的 ImageField。

    读取本地图片文件，通过 Django 的 File 包装后赋值到指定字段。
    调用方需在赋值后调用 instance.save() 持久化。

    Args:
        instance: Django 模型实例（需包含名为 field_name 的 ImageField）。
        field_name: ImageField 字段名。
        image_path: 本地图片绝对路径。

    Returns:
        True 表示赋值成功，False 表示文件不存在或字段无效。
    """
    if not image_path or not Path(image_path).exists():
        return False

    image_path = Path(image_path)
    try:
        # 生成唯一文件名避免冲突
        ext = image_path.suffix or ".jpg"
        unique_name = f"{uuid.uuid4().hex[:12]}{ext}"

        with open(image_path, "rb") as f:
            django_file = File(f, name=unique_name)
            getattr(instance, field_name).save(unique_name, django_file, save=False)

        logger.debug("图片已赋值 {}.{} <- {}", type(instance).__name__, field_name, image_path.name)
        return True
    except Exception as exc:
        logger.warning("图片赋值失败 {}.{}: {}", type(instance).__name__, field_name, exc)
        return False


def fetch_seed_image(
    keyword: str,
    *,
    user=None,
    category: str = "image",
    original_name: str | None = None,
):
    """从 Pixabay 下载图片并创建 FileEntry 记录。

    适用于需要文件管理记录的场景（如头像、独立文件资源）。
    对于直接赋值给 ImageField 的场景，推荐使用 ``get_cached_image_path`` + ``assign_image_to_field``。

    Args:
        keyword: Pixabay 搜索关键词。
        user: 上传者（User 实例）。
        category: 文件分类（默认 "image"）。
        original_name: 原始文件名（默认用关键词生成）。

    Returns:
        FileEntry 实例；失败时返回 None。
    """
    image_path = get_cached_image_path(keyword)
    if image_path is None:
        return None

    from apps.files.models import FileEntry
    from utils.file_helpers import generate_unique_filename

    image_path = Path(image_path)
    name = original_name or f"{keyword.replace(' ', '_')}{image_path.suffix}"
    unique_name = generate_unique_filename(name)

    try:
        with open(image_path, "rb") as f:
            django_file = File(f, name=unique_name)
            entry = FileEntry.objects.create(
                uploader=user,
                original_name=name,
                file=django_file,
                category=category,
                size=image_path.stat().st_size,
                content_type="image/jpeg",
            )
        logger.info("FileEntry 已创建: id={} keyword={}", entry.pk, keyword)
        return entry
    except Exception as exc:
        logger.warning("FileEntry 创建失败 keyword='{}': {}", keyword, exc)
        return None
