"""文件管理模型。

FileEntry 记录每一次上传的元数据，物理文件存于 MEDIA_ROOT 下：
    uploads/<上传者id>/<YYYYmm>/<uuid>.<ext>
原始文件名、大小、MIME、分类均入库保存，展示与检索不依赖物理路径。
"""

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone

from utils.constants import ALLOWED_FILE_EXTENSIONS
from utils.file_helpers import generate_unique_filename, get_extension


class FileCategory(models.TextChoices):
    """文件分类，供筛选与后续业务模块区分用途。"""

    AVATAR = "avatar", "头像"
    IMAGE = "image", "图片"
    DOCUMENT = "document", "文档"
    OTHER = "other", "其他"


def user_upload_path(instance: "FileEntry", filename: str) -> str:
    """按 上传者 / 年月 分目录，文件名用 UUID 去重。"""
    unique_name = generate_unique_filename(filename)
    stamp = timezone.localtime(instance.uploaded_at or timezone.now())
    return f"uploads/{instance.uploader_id}/{stamp:%Y%m}/{unique_name}"


class FileEntry(models.Model):
    """文件上传记录。"""

    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="files",
        verbose_name="上传者",
    )
    original_name = models.CharField("原始文件名", max_length=255)
    file = models.FileField(
        "文件",
        upload_to=user_upload_path,
        validators=[FileExtensionValidator(sorted(ALLOWED_FILE_EXTENSIONS))],
    )
    category = models.CharField(
        "分类",
        max_length=16,
        choices=FileCategory.choices,
        default=FileCategory.OTHER,
    )
    size = models.BigIntegerField("大小(字节)", default=0)
    content_type = models.CharField("MIME 类型", max_length=128, blank=True)
    uploaded_at = models.DateTimeField("上传时间", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "文件"
        verbose_name_plural = "文件"
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return self.original_name

    @property
    def extension(self) -> str:
        """文件扩展名（含点），取自原始文件名。"""
        return get_extension(self.original_name)

    @property
    def is_image(self) -> bool:
        """是否为图片（用于列表缩略预览）。"""
        return self.category == FileCategory.IMAGE or self.extension in {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".webp",
            ".bmp",
        }
