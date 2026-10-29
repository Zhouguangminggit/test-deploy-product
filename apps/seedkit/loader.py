"""统一 YAML 配置加载与 Schema 校验（fail-fast）。

配置文件默认路径 ``settings.SEEDKIT_CONFIG``（seeds/seed_data.yml），层级为
``modules → models → rows``。本模块只负责「读取 + 校验 + 结构化」，不写库：
任一校验不通过即抛 ``SeedConfigError``，整体报错、不落一条数据，把问题挡在执行前。

校验覆盖：
- 顶层结构（version / modules）与模块、模型、行的基本形态；
- ``model`` 能解析为已安装模型；行内键是模型真实字段（拒绝未知字段与反向关系）；
- 必填字段（editable、无 default、非 null/blank 的具体字段）在每行均已提供；
- 外键 / 多对多引用语法 ``ref: "<app>.<Model>.<键>"``、目标模型与关联模型一致、
  且不指向「后声明」的模型（被引用模型必须先声明，杜绝悬空引用）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from django.apps import apps
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db import models


class SeedConfigError(Exception):
    """YAML 配置非法（结构、字段、引用等）。message 需指明模块 / 模型 / 行号。"""


@dataclass
class ImageSeed:
    """单个图片字段的填充配置。"""

    field: str
    keywords_from: str | None = None  # 关键词取自行内该字段的值
    keywords: str | None = None  # 固定回退关键词


@dataclass
class ModelSeed:
    """一个模型的种子配置。"""

    label: str  # "app_label.ModelName"
    model: type[models.Model]
    rows: list[dict[str, Any]]
    images: list[ImageSeed] = field(default_factory=list)
    order: int = 0  # 全局扁平声明顺序，用于引用先后校验


@dataclass
class ModuleSeed:
    """一个业务模块的种子配置（--module 过滤单位）。"""

    name: str
    models: list[ModelSeed] = field(default_factory=list)


@dataclass
class SeedConfig:
    """解析后的完整配置。"""

    version: int = 1
    modules: list[ModuleSeed] = field(default_factory=list)

    def module_names(self) -> list[str]:
        return [m.name for m in self.modules]

    def get_module(self, name: str) -> ModuleSeed | None:
        return next((m for m in self.modules if m.name == name), None)

    @property
    def is_empty(self) -> bool:
        return not self.modules


# ----------------------------- 模型字段辅助 -----------------------------
def _natural_key_field(model: type[models.Model]) -> models.Field | None:
    """返回模型的首个「唯一非主键」字段，作为 ref 默认匹配键；无则 None。"""
    for f in model._meta.concrete_fields:
        if f.primary_key:
            continue
        if getattr(f, "unique", False):
            return f
    return None


def _required_field_names(model: type[models.Model], image_fields: set[str]) -> set[str]:
    """计算每行必须提供的字段名集合。

    规则：editable、非自增主键、无 default、且 null/blank 均为假的具体字段。
    由图片配置负责填充的字段（image_fields）从必填集中剔除。
    """
    required: set[str] = set()
    for f in model._meta.concrete_fields:
        if f.name in image_fields:
            continue
        if f.primary_key and isinstance(f, models.AutoField):
            continue
        if not f.editable:
            continue
        if f.has_default():
            continue
        if f.null or f.blank:
            continue
        required.add(f.name)
    return required


def _parse_ref(ref: Any, *, ctx: str) -> tuple[str, str, str]:
    """解析 ``"<app>.<Model>.<键>"``，返回 (app_label, model_name, key)。"""
    if not isinstance(ref, str):
        raise SeedConfigError(f"{ctx}：引用必须是字符串，得到 {ref!r}")
    parts = ref.split(".")
    if len(parts) < 3:
        raise SeedConfigError(f"{ctx}：非法引用 {ref!r}，应形如 '<app>.<Model>.<键>'")
    app_label, model_name = parts[0], parts[1]
    key = ".".join(parts[2:])
    if not key:
        raise SeedConfigError(f"{ctx}：引用 {ref!r} 缺少键值")
    return app_label, model_name, key


def _resolve_model(app_label: str, model_name: str, *, ctx: str) -> type[models.Model]:
    try:
        return apps.get_model(app_label, model_name)
    except (LookupError, ValueError) as exc:
        raise SeedConfigError(f"{ctx}：无法解析模型 '{app_label}.{model_name}'（{exc}）") from exc


# ----------------------------- 行 / 引用校验 -----------------------------
def _validate_ref_value(
    ref: Any,
    *,
    related_model: type[models.Model],
    field_name: str,
    ctx: str,
    declared_order: dict[str, int],
    current_order: int,
) -> None:
    """校验单条 ref 指向的模型与关联模型一致、且不指向后声明的模型。"""
    app_label, model_name, _key = _parse_ref(ref, ctx=f"{ctx} 字段 '{field_name}'")
    target = _resolve_model(app_label, model_name, ctx=f"{ctx} 字段 '{field_name}'")
    if target._meta.label_lower != related_model._meta.label_lower:
        raise SeedConfigError(
            f"{ctx} 字段 '{field_name}'：引用指向 {app_label}.{model_name}，"
            f"但关联模型是 {related_model._meta.app_label}.{related_model.__name__}"
        )
    target_label = f"{app_label}.{model_name}"
    declared = declared_order.get(target_label.lower())
    if declared is not None and declared > current_order:
        raise SeedConfigError(
            f"{ctx} 字段 '{field_name}'：引用了后声明的模型 '{target_label}'，"
            "被引用模型必须在 YAML 中先声明"
        )


def _validate_row(
    model_seed: ModelSeed,
    row: dict[str, Any],
    row_no: int,
    declared_order: dict[str, int],
) -> None:
    """校验单行数据：字段存在性、必填、引用合法性。"""
    model = model_seed.model
    ctx = f"模型 {model_seed.label} 第 {row_no} 行"
    image_fields = {img.field for img in model_seed.images}

    for key, value in row.items():
        if key == "_key":
            if not isinstance(value, (str, int)):
                raise SeedConfigError(f"{ctx}：_key 必须是字符串或整数，得到 {value!r}")
            continue
        try:
            field_obj = model._meta.get_field(key)
        except FieldDoesNotExist as exc:
            raise SeedConfigError(f"{ctx}：未知字段 '{key}'（{exc}）") from exc

        # 反向关系不可作为写入字段
        if field_obj.auto_created and not field_obj.concrete:
            raise SeedConfigError(f"{ctx}：'{key}' 是反向关系，不能作为写入字段")

        if isinstance(field_obj, models.ManyToManyField):
            _validate_m2m_value(
                field_obj,
                value,
                ctx=ctx,
                declared_order=declared_order,
                current_order=model_seed.order,
            )
        elif isinstance(field_obj, models.ForeignKey):
            _validate_fk_value(
                field_obj,
                value,
                ctx=ctx,
                declared_order=declared_order,
                current_order=model_seed.order,
            )
        elif (
            isinstance(field_obj, models.FileField)
            and isinstance(value, dict)
            and "keywords" not in value
        ):
            # 图片字段行级覆盖：{keywords: "..."}，必须显式给出关键词
            raise SeedConfigError(f"{ctx}：图片字段 '{key}' 的覆盖配置必须含 'keywords'")

    # 必填字段校验
    required = _required_field_names(model, image_fields)
    missing = required - set(row.keys())
    if missing:
        raise SeedConfigError(f"{ctx}：缺少必填字段 {sorted(missing)}")


def _validate_fk_value(
    field_obj: models.ForeignKey,
    value: Any,
    *,
    ctx: str,
    declared_order: dict[str, int],
    current_order: int,
) -> None:
    """外键值：``{ref: "..."}`` 或标量主键。"""
    if isinstance(value, dict):
        if "ref" not in value:
            raise SeedConfigError(f"{ctx}：外键字段 '{field_obj.name}' 的 dict 值必须含 'ref'")
        _validate_ref_value(
            value["ref"],
            related_model=field_obj.related_model,
            field_name=field_obj.name,
            ctx=ctx,
            declared_order=declared_order,
            current_order=current_order,
        )
    # 标量视为直接指定主键，运行期解析，无需加载期校验


def _validate_m2m_value(
    field_obj: models.ManyToManyField,
    value: Any,
    *,
    ctx: str,
    declared_order: dict[str, int],
    current_order: int,
) -> None:
    """多对多值：``{refs: [...]}``、``[{ref: ...}, ...]`` 或标量列表。"""
    items: Any
    if isinstance(value, dict):
        if "refs" not in value:
            raise SeedConfigError(f"{ctx}：多对多字段 '{field_obj.name}' 的 dict 值必须含 'refs'")
        items = value["refs"]
    else:
        items = value
    if not isinstance(items, list):
        raise SeedConfigError(f"{ctx}：多对多字段 '{field_obj.name}' 必须是列表")
    for item in items:
        if isinstance(item, dict) and "ref" in item:
            _validate_ref_value(
                item["ref"],
                related_model=field_obj.related_model,
                field_name=field_obj.name,
                ctx=ctx,
                declared_order=declared_order,
                current_order=current_order,
            )


def _validate_images(model_seed: ModelSeed, ctx: str) -> None:
    """校验模型级图片配置：字段必须是 FileField/ImageField。"""
    model = model_seed.model
    for img in model_seed.images:
        try:
            field_obj = model._meta.get_field(img.field)
        except FieldDoesNotExist as exc:
            raise SeedConfigError(f"{ctx}：图片字段 '{img.field}' 不存在（{exc}）") from exc
        if not isinstance(field_obj, models.FileField):
            raise SeedConfigError(f"{ctx}：'{img.field}' 不是图片/文件字段")
        if img.keywords_from:
            try:
                model._meta.get_field(img.keywords_from)
            except FieldDoesNotExist as exc:
                raise SeedConfigError(
                    f"{ctx}：图片 '{img.field}' 的 keywords_from 字段 '{img.keywords_from}' 不存在"
                ) from exc


# ----------------------------- 顶层加载 -----------------------------
def _parse_model_entry(
    module_name: str, entry: Any, order: int, declared_order: dict[str, int]
) -> ModelSeed:
    if not isinstance(entry, dict):
        raise SeedConfigError(
            f"模块 '{module_name}'：models 项必须是映射，得到 {type(entry).__name__}"
        )
    label = entry.get("model")
    if not isinstance(label, str) or "." not in label:
        raise SeedConfigError(
            f"模块 '{module_name}'：模型项缺少合法 'model'（应为 'app_label.Model'）"
        )
    app_label, model_name = label.split(".", 1)
    model = _resolve_model(app_label, model_name, ctx=f"模块 '{module_name}'")

    rows = entry.get("rows", [])
    if not isinstance(rows, list):
        raise SeedConfigError(f"模型 {label}：'rows' 必须是列表")

    raw_images = entry.get("images", []) or []
    if not isinstance(raw_images, list):
        raise SeedConfigError(f"模型 {label}：'images' 必须是列表")
    images: list[ImageSeed] = []
    for item in raw_images:
        if not isinstance(item, dict) or "field" not in item:
            raise SeedConfigError(f"模型 {label}：images 项必须是含 'field' 的映射")
        images.append(
            ImageSeed(
                field=item["field"],
                keywords_from=item.get("keywords_from"),
                keywords=item.get("keywords"),
            )
        )

    seed = ModelSeed(
        label=f"{model._meta.app_label}.{model.__name__}",
        model=model,
        rows=rows,
        images=images,
        order=order,
    )
    _validate_images(seed, ctx=f"模型 {label}")
    return seed


def load_config(path: str | Path | None = None) -> SeedConfig:
    """加载并校验 YAML 配置，返回 ``SeedConfig``。

    - 文件不存在或内容为空 → 返回空配置（modules=[]），调用方据此输出「无可执行模块」；
    - 结构 / 字段 / 引用非法 → 抛 ``SeedConfigError``（fail-fast，不落一条数据）。
    """
    config_path = Path(path) if path is not None else Path(getattr(settings, "SEEDKIT_CONFIG", ""))
    if not config_path.exists():
        return SeedConfig()

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SeedConfigError(f"YAML 解析失败（{config_path}）：{exc}") from exc

    if raw is None:
        return SeedConfig()
    if not isinstance(raw, dict):
        raise SeedConfigError("配置顶层必须是映射（含 version / modules）")

    version = int(raw.get("version", 1))
    modules_raw = raw.get("modules") or {}
    if not isinstance(modules_raw, dict):
        raise SeedConfigError("'modules' 必须是映射：模块名 → {models: [...]}")

    # 第一遍：解析所有模型并登记扁平声明顺序（label.lower() → order）
    modules: list[ModuleSeed] = []
    declared_order: dict[str, int] = {}
    order = 0
    for module_name, module_body in modules_raw.items():
        if not isinstance(module_body, dict):
            raise SeedConfigError(f"模块 '{module_name}'：配置必须是映射（含 models）")
        models_raw = module_body.get("models") or []
        if not isinstance(models_raw, list):
            raise SeedConfigError(f"模块 '{module_name}'：'models' 必须是列表")
        module_seed = ModuleSeed(name=str(module_name))
        for entry in models_raw:
            seed = _parse_model_entry(module_name, entry, order, declared_order)
            declared_order.setdefault(seed.label.lower(), order)
            module_seed.models.append(seed)
            order += 1
        modules.append(module_seed)

    # 第二遍：逐行校验（此时 declared_order 已完整，可判定引用先后）
    for module_seed in modules:
        for model_seed in module_seed.models:
            for row_no, row in enumerate(model_seed.rows, start=1):
                if not isinstance(row, dict):
                    raise SeedConfigError(
                        f"模型 {model_seed.label} 第 {row_no} 行：必须是映射，得到 {type(row).__name__}"
                    )
                _validate_row(model_seed, row, row_no, declared_order)

    return SeedConfig(version=version, modules=modules)
