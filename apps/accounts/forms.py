"""用户账户表单。

登录 / 注册 / 资料编辑 / 修改密码。统一为输入控件注入 DaisyUI `input` 类，
错误信息由模板中的 `.form-error` 渲染，故此处不重复处理样式之外的逻辑。
"""

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    UserCreationForm,
)

from utils.validators import validate_phone, validate_username

from .models import User

# DaisyUI 文本输入样式，注入到各控件的 class
INPUT_CLASS = "input input-bordered w-full"


def _apply_input_classes(form: forms.BaseForm) -> None:
    """为表单所有字段控件统一附加 DaisyUI input 类。"""
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, (forms.CheckboxInput, forms.FileInput)):
            continue
        existing = widget.attrs.get("class", "")
        widget.attrs["class"] = f"{existing} {INPUT_CLASS}".strip()


class LoginForm(AuthenticationForm):
    """登录表单（用户名 + 密码）。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_input_classes(self)


class RegisterForm(UserCreationForm):
    """注册表单：用户名、昵称、密码、确认密码。"""

    nickname = forms.CharField(
        label="昵称",
        max_length=50,
        required=True,
        help_text="展示在导航栏的个人昵称",
    )

    class Meta:
        model = User
        fields = ("username", "nickname")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_input_classes(self)

    def clean_username(self) -> str:
        username = self.cleaned_data["username"]
        return validate_username(username)

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.nickname = self.cleaned_data["nickname"]
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    """个人资料编辑：昵称、头像、邮箱、手机号。"""

    class Meta:
        model = User
        fields = ("nickname", "avatar", "email", "phone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_input_classes(self)
        # 头像控件走 DaisyUI file input 样式
        avatar_widget = self.fields["avatar"].widget
        avatar_widget.attrs["class"] = "file-input file-input-bordered w-full"

    def clean_phone(self) -> str:
        phone = self.cleaned_data.get("phone", "")
        if phone:
            return validate_phone(phone)
        return phone


class PasswordUpdateForm(PasswordChangeForm):
    """修改密码（复用 Django 内置旧密码校验与强度校验）。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_input_classes(self)
