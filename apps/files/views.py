"""文件管理视图（函数视图 + 模板渲染）。

上传 / 列表 / 下载 / 删除。可见性与访问控制：普通用户仅限自己的文件，
管理员（staff）可见并可管理全部文件。落盘统一走 services.save_upload。
"""

import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from utils.pagination import paginate_from_request

from .forms import FileUploadForm
from .models import FileCategory
from .selectors import get_accessible_file, visible_files
from .services import delete_file, save_upload


@login_required
def list_view(request: HttpRequest) -> HttpResponse:
    """文件列表 + 上传表单。"""
    category = request.GET.get("category") or ""
    entries = visible_files(request.user, category=category or None)
    page_result = paginate_from_request(entries, request)

    context = {
        "page_result": page_result,
        "form": FileUploadForm(),
        "categories": _category_options(),
        "active_category": category,
    }
    return render(request, "files/list.html", context)


@login_required
def upload_view(request: HttpRequest) -> HttpResponse:
    """处理上传（仅 POST），成功后回到列表页。"""
    if request.method != "POST":
        return redirect(reverse("files:list"))

    form = FileUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, _first_error(form))
        return redirect(reverse("files:list"))

    save_upload(
        form.cleaned_data["file"],
        user=request.user,
        category=form.cleaned_data["category"],
    )
    messages.success(request, "上传成功")
    return redirect(reverse("files:list"))


@login_required
def download_view(request: HttpRequest, pk: int) -> HttpResponse:
    """下载文件：校验归属后以原文件名返回附件。"""
    entry = get_accessible_file(request.user, pk)
    if entry is None or not entry.file:
        raise Http404("文件不存在或无权访问")

    if not os.path.exists(entry.file.path):
        raise Http404("文件已丢失")

    response = FileResponse(
        entry.file.open("rb"),
        as_attachment=True,
        filename=entry.original_name,
    )
    return response


@login_required
def delete_view(request: HttpRequest, pk: int) -> HttpResponse:
    """删除文件（仅 POST）：普通用户删自己的，管理员可删任意。"""
    if request.method != "POST":
        return redirect(reverse("files:list"))

    entry = get_accessible_file(request.user, pk)
    if entry is None:
        raise Http404("文件不存在或无权访问")

    delete_file(entry)
    messages.success(request, "文件已删除")
    return redirect(reverse("files:list"))


def _category_options() -> list[dict]:
    """供模板筛选栏使用的分类选项（含"全部"）。"""
    options = [{"value": "", "label": "全部"}]
    options += [{"value": value, "label": label} for value, label in FileCategory.choices]
    return options


def _first_error(form: FileUploadForm) -> str:
    """提取表单首条错误信息用于提示。"""
    for errors in form.errors.values():
        if errors:
            return errors[0]
    return "上传失败"
