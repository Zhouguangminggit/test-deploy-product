"""用户账户视图（函数视图 + 模板渲染）。

登录 / 注册 / 退出 / 个人中心。业务逻辑下沉 services，视图只负责编排请求。
"""

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.audit.decorators import log_operation
from apps.audit.models import OperationAction
from utils.decorators import anonymous_required

from .forms import LoginForm, PasswordUpdateForm, ProfileForm, RegisterForm
from .services import change_password, register_user, update_profile


@anonymous_required
@log_operation(OperationAction.LOGIN, module="accounts")
def login_view(request: HttpRequest) -> HttpResponse:
    """登录：用户名 + 密码。成功后回跳 next 或首页。"""
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        messages.success(request, f"欢迎回来，{user.display_name}")
        next_url = request.POST.get("next") or request.GET.get("next") or "/"
        return redirect(next_url)
    return render(request, "accounts/login.html", {"form": form})


@anonymous_required
@log_operation(OperationAction.REGISTER, module="accounts")
def register_view(request: HttpRequest) -> HttpResponse:
    """注册：成功后自动登录并进入个人中心。"""
    form = RegisterForm(data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        # 业务逻辑下沉 service：创建用户（含哈希密码）并发送注册欢迎通知
        user = register_user(
            username=form.cleaned_data["username"],
            nickname=form.cleaned_data["nickname"],
            password=form.cleaned_data["password1"],
        )
        login(request, user)
        messages.success(request, "注册成功，欢迎加入！")
        return redirect("accounts:profile")
    return render(request, "accounts/register.html", {"form": form})


@login_required
@log_operation(OperationAction.LOGOUT, module="accounts")
def logout_view(request: HttpRequest) -> HttpResponse:
    """退出登录（仅接受 POST，避免GET预取导致的意外登出）。"""
    if request.method == "POST":
        logout(request)
        messages.info(request, "已安全退出")
    return redirect("/")


@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    """个人中心：资料展示 + 编辑（昵称/头像/邮箱/手机号）+ 修改密码。"""
    profile_form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    password_form = PasswordUpdateForm(request.user, data=None)

    if (
        request.method == "POST"
        and request.POST.get("form") == "profile"
        and profile_form.is_valid()
    ):
        update_profile(
            request.user,
            nickname=profile_form.cleaned_data["nickname"],
            email=profile_form.cleaned_data["email"],
            phone=profile_form.cleaned_data["phone"],
            avatar=request.FILES.get("avatar"),
        )
        messages.success(request, "资料已更新")
        return redirect("accounts:profile")

    if request.method == "POST" and request.POST.get("form") == "password":
        password_form = PasswordUpdateForm(request.user, data=request.POST)
        if password_form.is_valid():
            change_password(
                request.user,
                old_password=password_form.cleaned_data["old_password"],
                new_password=password_form.cleaned_data["new_password1"],
            )
            messages.success(request, "密码已修改")
            return redirect("accounts:profile")

    context = {
        "profile_form": profile_form,
        "password_form": password_form,
        "profile_messages": [
            error
            for errors in profile_form.errors.values()
            for error in errors
        ],
    }
    return render(request, "accounts/profile.html", context)
