"""文件管理表单。"""

from django import forms

from utils.constants import ALLOWED_FILE_EXTENSIONS, MAX_UPLOAD_SIZE
from utils.validators import validate_file_extension, validate_file_size

from .models import FileCategory

FILE_INPUT_CLASS = "file-input file-input-bordered w-full"
SELECT_CLASS = "select select-bordered w-full"


class FileUploadForm(forms.Form):
    """上传表单：选择文件 + 分类。校验大小与扩展名后交由 services 落盘。"""

    file = forms.FileField(label="选择文件")
    category = forms.ChoiceField(
        label="分类",
        choices=FileCategory.choices,
        initial=FileCategory.OTHER,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].widget.attrs["class"] = FILE_INPUT_CLASS
        self.fields["category"].widget.attrs["class"] = SELECT_CLASS

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        validate_file_size(uploaded, MAX_UPLOAD_SIZE)
        validate_file_extension(getattr(uploaded, "name", ""), ALLOWED_FILE_EXTENSIONS)
        return uploaded

    def clean_category(self) -> str:
        category = self.cleaned_data.get("category") or FileCategory.OTHER
        return category
