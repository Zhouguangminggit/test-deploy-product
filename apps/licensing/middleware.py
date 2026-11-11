from urllib.parse import urlencode

from django.http import JsonResponse
from django.shortcuts import render

from .services import LicenseError, check_license

MESSAGES = {
    "NOT_ACTIVATED": "尚未激活，请联网输入授权码。",
    "INVALID_CACHE": "本地授权记录损坏，请重新联网激活。",
    "CONFIG_ERROR": "授权配置错误，请联系售后。",
    "DEVICE_ERROR": "无法获取稳定的设备标识，请联系售后。",
    "INVALID_LICENSE": "授权码无效或不适用于本产品。",
    "DEVICE_LIMIT": "授权设备数量已满，更换设备请联系售后。",
    "DISABLED": "授权已停用，请联系售后。",
    "NOT_BOUND": "设备绑定已重置，请重新联网激活。",
    "EXPIRED": "离线授权已过期，请联网重试。",
    "CLOCK_ERROR": "系统时间异常，请校准时间并联网重试。",
    "TEMPORARY_UNAVAILABLE": "授权服务暂不可用，请检查网络后重试。",
}


class LicenseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info in ("/license/activate/", "/healthz/"):
            return self.get_response(request)
        try:
            check_license()
        except LicenseError as exc:
            if "text/html" not in request.headers.get("Accept", ""):
                return JsonResponse({"code": exc.code, "message": "产品授权不可用"}, status=403)
            link = "/license/activate/?" + urlencode({"next": request.get_full_path()})
            return render(
                request,
                "licensing/blocked.html",
                {
                    "code": exc.code,
                    "message": MESSAGES.get(exc.code, "授权不可用，请联系售后。"),
                    "activation_url": link,
                },
                status=403,
            )
        return self.get_response(request)
