"""前后台共用的站点品牌资源。"""

from django.conf import settings
from django.templatetags.static import static


def site_logo_url(request=None) -> str:
    """保留外部或根路径 URL，通过静态存储解析相对资源路径。"""
    logo = settings.SITE_LOGO.strip()
    if not logo or logo.startswith(("http://", "https://", "/")):
        return logo
    return static(logo)
