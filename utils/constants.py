"""全局常量。

集中管理跨模块复用的“魔法值”，避免硬编码散落各处。
如需按环境变化，请改用 settings（env 驱动），此处仅存放稳定常量。
"""

# ----------------------------- 分页 -----------------------------
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
PAGE_QUERY_PARAM = "page"
PAGE_SIZE_QUERY_PARAM = "page_size"

# ----------------------------- 文件上传 -----------------------------
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
ALLOWED_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".txt",
    ".md",
    ".csv",
    ".zip",
}
ALLOWED_FILE_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_DOCUMENT_EXTENSIONS

# ----------------------------- 日期时间格式 -----------------------------
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DATETIME_FORMAT_MINUTE = "%Y-%m-%d %H:%M"
DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"

# ----------------------------- 请求 / 响应 -----------------------------
REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_LENGTH = 32

# 统一响应状态码（业务码，非 HTTP 状态码）
RESPONSE_CODE_SUCCESS = 0
RESPONSE_CODE_ERROR = 1
