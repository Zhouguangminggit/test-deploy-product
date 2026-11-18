"""消息通知视图（函数视图 + 模板渲染）。

收件箱列表 / 详情（打开即已读） / 标记已读 / 全部已读 / 删除。
所有访问均需登录，且严格限定用户只能操作自己的收件记录。
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from utils.pagination import paginate_from_request

from . import selectors
from .services import delete_for_user, mark_all_read, mark_read


@login_required
def list_view(request: HttpRequest) -> HttpResponse:
    """收件箱：全部 / 仅未读切换，分页展示。"""
    state = "unread" if request.GET.get("state") == "unread" else "all"
    entries = selectors.inbox(request.user, only_unread=state == "unread")
    page_result = paginate_from_request(entries, request)

    context = {
        "page_result": page_result,
        "state": state,
        "unread_total": selectors.unread_count(request.user),
    }
    return render(request, "notifications/list.html", context)


@login_required
def detail_view(request: HttpRequest, pk: int) -> HttpResponse:
    """消息详情：打开即标记为已读。"""
    recipient = get_object_or_404(selectors.inbox(request.user), pk=pk)
    mark_read(recipient)
    return render(request, "notifications/detail.html", {"recipient": recipient})


@login_required
def mark_read_view(request: HttpRequest, pk: int) -> HttpResponse:
    """标记单条已读（POST）。"""
    if request.method == "POST":
        recipient = get_object_or_404(selectors.inbox(request.user), pk=pk)
        mark_read(recipient)
    return redirect(request.POST.get("next") or reverse("notifications:list"))


@login_required
def mark_all_read_view(request: HttpRequest) -> HttpResponse:
    """全部标记已读（POST）。"""
    if request.method == "POST":
        updated = mark_all_read(request.user)
        messages.success(request, f"已将 {updated} 条消息标记为已读")
    return redirect(reverse("notifications:list"))


@login_required
def delete_view(request: HttpRequest, pk: int) -> HttpResponse:
    """删除单条收件记录（POST，软删除）。"""
    if request.method == "POST":
        recipient = get_object_or_404(selectors.inbox(request.user), pk=pk)
        delete_for_user(recipient)
        messages.success(request, "消息已删除")
    return redirect(reverse("notifications:list"))
