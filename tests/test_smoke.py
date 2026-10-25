"""框架冒烟测试：健康检查、自定义错误页、模板渲染管线。"""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, override_settings

from utils.pagination import paginate


def _make_request(path="/"):
    """构造带 user / request_id 的伪请求，满足各上下文处理器的需要。"""
    request = RequestFactory().get(path)
    request.user = AnonymousUser()
    request.request_id = "test-request-id"
    return request


def test_healthz_endpoint(client):
    resp = client.get("/healthz/")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    # 中间件应回写 X-Request-ID 响应头
    assert resp.headers.get("X-Request-ID")


@override_settings(DEBUG=False)
def test_custom_404_page(client):
    resp = client.get("/definitely-not-exists/")
    assert resp.status_code == 404
    assert b"404" in resp.content


@pytest.mark.parametrize(
    "template_name",
    [
        "base.html",
        "layouts/frontend.html",
        "errors/403.html",
        "errors/404.html",
        "errors/500.html",
        "includes/navbar.html",
        "includes/footer.html",
        "includes/messages.html",
        "includes/confirm_modal.html",
    ],
)
def test_templates_render(template_name):
    html = render_to_string(template_name, request=_make_request())
    assert isinstance(html, str)


def test_pagination_include_renders():
    pager = paginate(list(range(50)), page=3, page_size=5)
    html = render_to_string(
        "includes/pagination.html",
        {"page_result": pager},
        request=_make_request(),
    )
    assert "上一页" in html
    assert "下一页" in html


def test_custom_template_tags_available():
    """common_tags 已注册为内置标签库，模板中可直接使用。"""
    html = render_to_string(
        "errors/404.html",
        request=_make_request(),
    )
    # base.html 应引入 Tailwind 编译产物路径
    assert "css/dist/base.css" in html
