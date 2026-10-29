"""种子填充引擎：把 YAML 行数据写入数据库、解析引用、分配图片。

设计要点：
- 模块级 ``transaction.atomic()``：一个模块内任一模型失败则整模块回滚，
  成功模块已提交，从而实现干净的「部分成功」语义；
- 引用解析：优先命中本次运行已创建对象的注册表，未命中回退查库
  （支持引用 init-data 等既有数据），保证「手机 / 电脑挂电子器材、书籍挂图书」的关联真实性；
- 图片：按行解析出的关键词调 utils.pixabay 检索下载，同字段多行按结果顺序轮换，
  避免全部同图；关键词优先级为 行内 {keywords} > 模型级 keywords_from > 模型级 keywords。

本模块只依赖传入的 ``log``（具备 info/warning/error 方法）与 ``stats`` 累加器，
不直接触碰 SeedRun / SeedRunLog，便于脱离运行记录单独测试。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from django.core.files import File
from django.db import models, transaction
from loguru import logger

from utils import pixabay

from .loader import ModelSeed, ModuleSeed, SeedConfigError, _natural_key_field, _parse_ref


class RunLog(Protocol):
    """运行日志接口（services.RunLogger 实现，双写 DB + loguru）。"""

    def info(self, message: str) -> None: ...
    def warning(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...


@dataclass
class SeedStats:
    """一次运行 / 模块的统计累加器。"""

    created: int = 0
    skipped: int = 0
    images: int = 0


def _coerce(field_obj: models.Field, value: Any) -> Any:
    """把 YAML 标量按字段类型转换（日期 / 时间 / Decimal 等）。"""
    if value is None:
        return None
    if isinstance(
        field_obj,
        (models.DateField, models.DateTimeField, models.TimeField, models.DecimalField),
    ):
        return field_obj.to_python(value)
    return value


def _resolve_ref(
    related_model: type[models.Model],
    ref: str,
    registry: dict[str, dict[str, Any]],
) -> Any:
    """解析 ``"<app>.<Model>.<键>"`` 引用为模型实例。

    先查本次运行注册表（label_lower → {键: 实例}），未命中回退数据库：
    依次按「首个唯一字段」与主键匹配。找不到抛 SeedConfigError。
    """
    _app, _model_name, key = _parse_ref(ref, ctx="引擎解析引用")
    label_lower = related_model._meta.label_lower
    bucket = registry.get(label_lower, {})
    if key in bucket:
        return bucket[key]

    obj = None
    natural = _natural_key_field(related_model)
    if natural is not None:
        obj = related_model.objects.filter(**{natural.name: key}).first()
    if obj is None and str(key).lstrip("-").isdigit():
        obj = related_model.objects.filter(pk=key).first()
    if obj is None:
        raise SeedConfigError(f"引用未找到：'{ref}'（{related_model.__name__} 中无匹配记录）")

    bucket[key] = obj
    registry[label_lower] = bucket
    return obj


def _resolve_m2m(
    field_obj: models.ManyToManyField,
    value: Any,
    registry: dict[str, dict[str, Any]],
) -> list[Any]:
    """解析多对多值为实例列表，支持 ``{refs: [...]}``、``[{ref:...}]`` 与标量列表。"""
    related_model = field_obj.related_model
    items = value["refs"] if isinstance(value, dict) else value
    resolved: list[Any] = []
    for item in items or []:
        if isinstance(item, dict) and "ref" in item:
            resolved.append(_resolve_ref(related_model, item["ref"], registry))
        elif isinstance(item, str) and item.count(".") >= 2:
            resolved.append(_resolve_ref(related_model, item, registry))
        elif str(item).lstrip("-").isdigit():
            obj = related_model.objects.filter(pk=item).first()
            if obj is None:
                raise SeedConfigError(f"多对多引用未找到：{field_obj.name} pk={item}")
            resolved.append(obj)
        else:
            raise SeedConfigError(f"多对多字段 '{field_obj.name}' 存在无法解析的项：{item!r}")
    return resolved


def _build_row(
    model_seed: ModelSeed,
    row: dict[str, Any],
    registry: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, list[Any]], dict[str, Any]]:
    """把一行 YAML 拆成 (create 关键字参数, 多对多映射, 图片关键词覆盖)。"""
    model = model_seed.model
    create_kwargs: dict[str, Any] = {}
    m2m_map: dict[str, list[Any]] = {}
    image_overrides: dict[str, Any] = {}

    for key, value in row.items():
        if key == "_key":
            continue
        field_obj = model._meta.get_field(key)
        if isinstance(field_obj, models.ManyToManyField):
            m2m_map[field_obj.name] = _resolve_m2m(field_obj, value, registry)
        elif isinstance(field_obj, models.ForeignKey):
            if isinstance(value, dict) and "ref" in value:
                create_kwargs[field_obj.name] = _resolve_ref(
                    field_obj.related_model, value["ref"], registry
                )
            else:
                create_kwargs[field_obj.name] = value  # 标量视为主键
        elif isinstance(field_obj, models.FileField) and isinstance(value, dict):
            image_overrides[field_obj.name] = value.get("keywords")
        else:
            create_kwargs[field_obj.name] = _coerce(field_obj, value)
    return create_kwargs, m2m_map, image_overrides


def _image_filename(model_seed: ModelSeed, field_name: str, suffix: str) -> str:
    """生成唯一图片文件名（storage 会在 upload_to 目录下去重，此处再保证不撞名）。"""
    slug = model_seed.model._meta.label_lower.replace(".", "_")
    return f"seed_{slug}_{field_name}_{uuid.uuid4().hex[:12]}{suffix or '.jpg'}"


def _assign_images(
    model_seed: ModelSeed,
    instance: models.Model,
    row: dict[str, Any],
    image_overrides: dict[str, Any],
    cursor: dict[str, int],
    log: RunLog,
) -> int:
    """为实例的各图片字段检索并落盘图片，返回成功赋值数量。"""
    assigned = 0
    for img in model_seed.images:
        keyword = image_overrides.get(img.field)
        if keyword is None:
            if img.keywords_from:
                keyword = row.get(img.keywords_from)
            elif img.keywords:
                keyword = img.keywords
        keyword = str(keyword).strip() if keyword is not None else ""
        if not keyword:
            continue

        results = pixabay.search_images(keyword)
        if not results:
            log.warning(
                f"{model_seed.label} 图片字段 '{img.field}' 关键词 '{keyword}' 无结果，跳过"
            )
            continue
        pick = results[cursor.get(img.field, 0) % len(results)]
        cursor[img.field] = cursor.get(img.field, 0) + 1

        path = pixabay.download_image(pick)
        if path is None:
            log.warning(
                f"{model_seed.label} 图片字段 '{img.field}' 下载失败，跳过（关键词 '{keyword}'）"
            )
            continue

        filename = _image_filename(model_seed, img.field, path.suffix)
        with path.open("rb") as fh:
            getattr(instance, img.field).save(filename, File(fh), save=False)
        assigned += 1
    return assigned


def _register(
    model_seed: ModelSeed,
    instance: models.Model,
    row: dict[str, Any],
    registry: dict[str, dict[str, Any]],
) -> None:
    """把已创建实例登记进注册表，供后续行 ref 解析（键 + 主键双登记）。"""
    label_lower = model_seed.model._meta.label_lower
    bucket = registry.setdefault(label_lower, {})
    key = row.get("_key")
    if key is None:
        natural = _natural_key_field(model_seed.model)
        if natural is not None:
            key = getattr(instance, natural.attname)
    if key is not None:
        bucket[str(key)] = instance
    if instance.pk is not None:
        bucket[str(instance.pk)] = instance


def _seed_model(
    model_seed: ModelSeed,
    registry: dict[str, dict[str, Any]],
    stats: SeedStats,
    log: RunLog,
    module_name: str,
) -> None:
    """写入单个模型的所有行（调用方已保证在模块事务内）。"""
    model = model_seed.model
    cursor: dict[str, int] = {}
    created = 0
    for row_no, row in enumerate(model_seed.rows, start=1):
        create_kwargs, m2m_map, image_overrides = _build_row(model_seed, row, registry)
        try:
            instance = model(**create_kwargs)
            stats.images += _assign_images(model_seed, instance, row, image_overrides, cursor, log)
            instance.save()
            for field_name, objs in m2m_map.items():
                getattr(instance, field_name).set(objs)
        except SeedConfigError:
            raise
        except Exception as exc:  # noqa: BLE001 - 归一化为带行号的配置/写入错误
            raise SeedConfigError(
                f"{module_name}/{model_seed.label} 第 {row_no} 行写入失败：{exc}"
            ) from exc
        _register(model_seed, instance, row, registry)
        created += 1
    stats.created += created
    log.info(f"[{module_name}] {model_seed.label}：新增 {created} 条")


def seed_module(module: ModuleSeed, *, refresh: bool, log: RunLog) -> SeedStats:
    """执行单个模块的种子填充，返回统计。整模块在一个事务内，失败全回滚。"""
    stats = SeedStats()
    registry: dict[str, dict[str, Any]] = {}
    with transaction.atomic():
        if refresh:
            # 逆序删除（先子表后父表），规避外键约束
            for model_seed in reversed(module.models):
                deleted, _ = model_seed.model.objects.all().delete()
                log.info(f"[{module.name}] refresh 清空 {model_seed.label}（{deleted} 条）")
        for model_seed in module.models:
            if not refresh and model_seed.model.objects.exists():
                count = model_seed.model.objects.count()
                stats.skipped += count
                log.info(
                    f"[{module.name}] {model_seed.label}：已有 {count} 条，跳过（--refresh 可重填）"
                )
                continue
            _seed_model(model_seed, registry, stats, log, module.name)
    return stats


def run_config(config, *, modules: list[str] | None, refresh: bool, log: RunLog) -> SeedStats:
    """按配置执行全部（或指定）模块，返回累计统计。

    单个模块失败会记录错误并继续下一个模块；调用方据失败数量判定
    success / partial / failed。这里用 log.error 记录并把异常汇总抛出由 services 决策。
    """
    total = SeedStats()
    selected = [m for m in config.modules if not modules or m.name in modules]
    if modules:
        unknown = set(modules) - {m.name for m in config.modules}
        if unknown:
            raise SeedConfigError(f"指定的模块在 YAML 中不存在：{sorted(unknown)}")
    if not selected:
        log.warning("无可执行模块（YAML 未声明业务数据或 --module 未匹配）")
        return total

    failures: list[str] = []
    for module in selected:
        try:
            stats = seed_module(module, refresh=refresh, log=log)
        except Exception as exc:  # noqa: BLE001 - 模块级隔离，单模块失败不影响其他模块
            logger.exception("模块 {} 初始化失败", module.name)
            log.error(f"[{module.name}] 初始化失败，已回滚：{exc}")
            failures.append(module.name)
            continue
        total.created += stats.created
        total.skipped += stats.skipped
        total.images += stats.images

    if failures:
        raise SeedRunPartial(failures, total)
    return total


class SeedRunPartial(Exception):  # noqa: N818 - 表示「部分成功」结果信号（保留已成功模块），非纯错误，故不加 Error 后缀
    """部分模块失败：携带失败模块名与已成功部分的统计。"""

    def __init__(self, failed_modules: list[str], stats: SeedStats) -> None:
        self.failed_modules = failed_modules
        self.stats = stats
        super().__init__(f"部分模块初始化失败：{failed_modules}")
