"""文件业务逻辑（services）。

对外提供统一的落盘入口，供 files 视图与后续其他模块直接复用：
    from apps.files.services import save_upload, delete_file

save_upload 负责校验（大小 / 扩展名）并写入 FileEntry；
delete_file 负责物理文件与数据库记录的同步清理。
"""

from django.contrib.auth import get_user_model
from loguru import logger

from utils.constants import ALLOWED_FILE_EXTENSIONS
from utils.validators import validate_file_extension, validate_file_size

from .models import FileCategory, FileEntry

User = get_user_model()


def save_upload(
    file_obj,
    *,
    user: User,
    category: str = FileCategory.OTHER,
    original_name: str | None = None,
    max_bytes: int | None = None,
) -> FileEntry:
    """保存一次上传，返回创建的 FileEntry。

    - file_obj：Django UploadedFile / File 实例（需具备 name、size 属性）；
    - user：上传者；
    - category：分类（默认「其他」，其他模块可传 AVATAR / IMAGE 等）；
    - original_name：展示用原始文件名，缺省取 file_obj.name；
    - max_bytes：可选覆盖默认大小上限。

    校验失败抛出 django.core.exceptions.ValidationError，由调用方（表单 / 视图）处理。
    """
    name = original_name or getattr(file_obj, "name", "") or "file"

    if max_bytes is None:
        validate_file_size(file_obj)
    else:
        validate_file_size(file_obj, max_bytes)
    validate_file_extension(name, ALLOWED_FILE_EXTENSIONS)

    entry = FileEntry.objects.create(
        uploader=user,
        original_name=name,
        file=file_obj,
        category=category,
        size=getattr(file_obj, "size", 0) or 0,
        content_type=getattr(file_obj, "content_type", "") or "",
    )
    logger.info("文件上传成功：id={} name={} uploader={}", entry.pk, name, user.pk)
    return entry


def delete_file(entry: FileEntry) -> None:
    """删除文件记录并清理物理文件。物理删除失败不影响记录删除。"""
    entry_id = entry.pk
    try:
        if entry.file:
            entry.file.delete(save=False)
    except OSError as exc:
        logger.warning("物理文件删除失败：id={} err={}", entry_id, exc)
    entry.delete()
    logger.info("文件记录已删除：id={}", entry_id)
