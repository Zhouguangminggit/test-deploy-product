"""按声明顺序导入种子行，解析关系并保存关联素材。

版本 2 按数据库唯一键逐行补齐，所选模块共用事务。版本 1 保留模块级事务和整表跳过。
通过 Django storage 保存的本批文件会在事务失败时清理。
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.storage import Storage
from django.db import models, transaction
from loguru import logger
from PIL import Image

from utils import pixabay

from .loader import (
    ModelSeed,
    ModuleSeed,
    SeedConfig,
    SeedConfigError,
    _natural_key_field,
    _parse_ref,
    row_key,
)


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


@dataclass
class SeedReferences:
    lookups: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    objects: dict[tuple[str, str], models.Model] = field(default_factory=dict)


@dataclass
class SeedImagePool:
    """单次运行共用候选图，按关键词轮换并复用下载结果。"""

    searches: dict[str, list[pixabay.PixabayImage]] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    cursor: dict[str, int] = field(default_factory=dict)
    downloads: dict[int, Path | None] = field(default_factory=dict)

    def pick(self, keyword: str) -> tuple[Path | None, str]:
        if keyword not in self.searches:
            try:
                self.searches[keyword] = pixabay.search_images(keyword)
            except pixabay.PixabayError as exc:
                self.searches[keyword] = []
                self.errors[keyword] = str(exc)
        results = self.searches[keyword]
        if not results:
            reason = "无搜索结果" if pixabay.is_configured() else "未配置 PIXABAY_API_KEY"
            return None, self.errors.get(keyword, reason)

        for _ in range(min(3, len(results))):
            index = self.cursor.get(keyword, 0)
            self.cursor[keyword] = index + 1
            image = results[index % len(results)]
            if image.id not in self.downloads:
                self.downloads[image.id] = pixabay.download_image(image)
            if path := self.downloads[image.id]:
                return path, ""
        return None, "候选图下载失败"


@contextmanager
def _seed_transaction():
    saved_files: list[tuple[Storage, str]] = []
    try:
        with transaction.atomic():
            yield saved_files
    except BaseException:
        for storage, name in reversed(saved_files):
            try:
                storage.delete(name)
            except Exception:  # noqa: BLE001 - 保留原始写入错误并继续清理其他文件
                logger.exception("种子资源清理失败：{}", name)
        raise


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
    registry: SeedReferences,
) -> Any:
    """解析 ``"<app>.<Model>.<键>"`` 引用为模型实例。

    先查本次运行注册表（label_lower → {键: 实例}），未命中回退数据库：
    依次按「首个唯一字段」与主键匹配。找不到抛 SeedConfigError。
    """
    _app, _model_name, key = _parse_ref(ref, ctx="引擎解析引用")
    label_lower = related_model._meta.label_lower
    reference = (label_lower, key)
    if reference in registry.objects:
        return registry.objects[reference]

    obj = None
    manager = related_model._base_manager
    if reference in registry.lookups:
        obj = manager.filter(**registry.lookups[reference]).first()
    else:
        natural = _natural_key_field(related_model)
        if natural is not None:
            with suppress(ValueError, ValidationError):
                obj = manager.filter(**{natural.name: key}).first()
        if obj is None:
            with suppress(ValueError, ValidationError):
                obj = manager.filter(pk=key).first()
    if obj is None:
        raise SeedConfigError(f"引用未找到：'{ref}'（{related_model.__name__} 中无匹配记录）")

    registry.objects[reference] = obj
    return obj


def _resolve_m2m(
    field_obj: models.ManyToManyField,
    value: Any,
    registry: SeedReferences,
) -> list[Any]:
    """解析多对多值为实例列表，支持 ``{refs: [...]}``、``[{ref:...}]`` 与标量列表。"""
    related_model = field_obj.related_model
    items = value["refs"] if isinstance(value, dict) else value
    resolved: list[Any] = []
    for item in items or []:
        if isinstance(item, dict) and "ref" in item:
            resolved.append(_resolve_ref(related_model, item["ref"], registry))
        else:
            if isinstance(item, str) and item.count(".") >= 2:
                resolved.append(_resolve_ref(related_model, item, registry))
                continue
            obj = related_model._base_manager.filter(pk=item).first()
            if obj is None:
                raise SeedConfigError(f"多对多引用未找到：{field_obj.name} pk={item}")
            resolved.append(obj)
    return resolved


def _build_row(
    model_seed: ModelSeed,
    row: dict[str, Any],
    registry: SeedReferences,
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
                if (
                    value is not None
                    and not field_obj.related_model._base_manager.filter(
                        **{field_obj.target_field.name: value}
                    ).exists()
                ):
                    raise SeedConfigError(f"外键引用未找到：{field_obj.name}={value}")
                create_kwargs[field_obj.attname] = value
        elif isinstance(field_obj, models.FileField) and isinstance(value, dict):
            image_overrides[field_obj.name] = value
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
    pool: SeedImagePool,
    log: RunLog,
    assets: dict[str, Path],
    saved_files: list[tuple[Storage, str]],
    *,
    existing: bool,
) -> list[str]:
    """填充图片并返回成功赋值的字段。重复运行只补空白图片字段。"""
    assigned = []
    image_configs = {img.field: img for img in model_seed.images}
    for field_name in dict.fromkeys([*image_configs, *image_overrides]):
        if existing and getattr(instance, field_name):
            continue
        override = image_overrides.get(field_name, {})
        if "asset" in override:
            if existing:
                continue
            path = assets[override["asset"]]
            file_field = model_seed.model._meta.get_field(field_name)
            if isinstance(file_field, models.ImageField):
                with Image.open(path) as image:
                    image.verify()
            _save_resource(instance, field_name, path, path.name, saved_files, validate=True)
            assigned.append(field_name)
            continue
        if field_name in row and field_name not in image_overrides:
            continue
        img = image_configs.get(field_name)
        keyword = override.get("keywords")
        if keyword is None and img:
            value = instance
            if img.keywords_from:
                for attr in img.keywords_from.split("."):
                    value = getattr(value, attr, None)
                keyword = str(value).strip() if value is not None else ""
            keyword = keyword or img.keywords
        keyword = str(keyword).strip() if keyword is not None else ""
        if not keyword:
            continue

        path, reason = pool.pick(keyword)
        if path is None:
            log.warning(
                f"{model_seed.label} 图片字段 '{field_name}' 跳过：{reason}（关键词 '{keyword}'）"
            )
            continue

        filename = _image_filename(model_seed, field_name, path.suffix)
        _save_resource(instance, field_name, path, filename, saved_files)
        assigned.append(field_name)
    return assigned


def _save_resource(
    instance: models.Model,
    field_name: str,
    path: Path,
    filename: str,
    saved_files: list[tuple[Storage, str]],
    *,
    validate: bool = False,
) -> None:
    field_file = getattr(instance, field_name)
    with path.open("rb") as source:
        upload = File(source, name=filename)
        if validate:
            field_file.field.run_validators(upload)
        field_file.save(filename, upload, save=False)
        saved_files.append((field_file.storage, field_file.name))


def _check_existing_relations(
    instance: models.Model,
    create_kwargs: dict[str, Any],
    m2m_map: dict[str, list[Any]],
) -> None:
    """版本 2 复用记录前，核对 YAML 中显式声明的关系。"""
    for field_obj in instance._meta.concrete_fields:
        if not isinstance(field_obj, models.ForeignKey):
            continue
        if field_obj.name in create_kwargs:
            target = create_kwargs[field_obj.name]
            expected = field_obj.target_field.value_from_object(target)
        elif field_obj.attname in create_kwargs:
            expected = field_obj.target_field.to_python(create_kwargs[field_obj.attname])
        else:
            continue
        if getattr(instance, field_obj.attname) != expected:
            raise SeedConfigError(f"已有记录的外键 '{field_obj.name}' 与配置不一致")

    for name, targets in m2m_map.items():
        actual = set(getattr(instance, name).values_list("pk", flat=True))
        if actual != {target.pk for target in targets}:
            raise SeedConfigError(f"已有记录的多对多字段 '{name}' 与配置不一致")


def _seed_model(
    model_seed: ModelSeed,
    registry: SeedReferences,
    stats: SeedStats,
    log: RunLog,
    module_name: str,
    assets: dict[str, Path],
    saved_files: list[tuple[Storage, str]],
    pool: SeedImagePool,
) -> None:
    """写入单个模型的所有行（调用方已保证在模块事务内）。"""
    model = model_seed.model
    created, skipped = 0, 0
    for row_no, row in enumerate(model_seed.rows, start=1):
        try:
            create_kwargs, m2m_map, image_overrides = _build_row(model_seed, row, registry)
            identity = {name: create_kwargs[name] for name in model_seed.match_by}
            instance = (
                model._base_manager.select_for_update().filter(**identity).first()
                if identity
                else None
            )
            existing = instance is not None
            if existing:
                _check_existing_relations(instance, create_kwargs, m2m_map)
            else:
                instance = model(**create_kwargs)
            fields = _assign_images(
                model_seed,
                instance,
                row,
                image_overrides,
                pool,
                log,
                assets,
                saved_files,
                existing=existing,
            )
            stats.images += len(fields)
            if not existing:
                instance.save(force_insert=bool(identity))
                for field_name, objs in m2m_map.items():
                    getattr(instance, field_name).set(objs)
                created += 1
            else:
                if fields:
                    instance.save(update_fields=fields)
                skipped += 1
            key = row_key(model_seed, row)
            if not model_seed.match_by:
                if key is None and (natural := _natural_key_field(model)):
                    value = getattr(instance, natural.attname)
                    key = str(value) if value is not None else None
                registry.objects[(model._meta.label_lower, str(instance.pk))] = instance
            if key is not None:
                registry.objects[(model._meta.label_lower, key)] = instance
        except Exception as exc:  # noqa: BLE001 - 归一化为带行号的配置/写入错误
            raise SeedConfigError(
                f"{module_name}/{model_seed.label} 第 {row_no} 行写入失败：{exc}"
            ) from exc
    stats.created += created
    stats.skipped += skipped
    log.info(f"[{module_name}] {model_seed.label}：新增 {created} 条，跳过 {skipped} 条")


def seed_module(
    module: ModuleSeed,
    *,
    refresh: bool,
    log: RunLog,
    assets: dict[str, Path] | None = None,
    pool: SeedImagePool | None = None,
) -> SeedStats:
    """执行单个模块的种子填充，返回统计。整模块在一个事务内，失败全回滚。"""
    stats = SeedStats()
    registry = SeedReferences()
    pool = pool or SeedImagePool()
    with _seed_transaction() as saved_files:
        if refresh:
            # 逆序删除（先子表后父表），规避外键约束
            for model_seed in reversed(module.models):
                deleted, _ = model_seed.model.objects.all().delete()
                log.info(f"[{module.name}] refresh 清空 {model_seed.label}（{deleted} 条）")
        for model_seed in module.models:
            if not refresh and not model_seed.match_by and model_seed.model.objects.exists():
                count = model_seed.model.objects.count()
                stats.skipped += count
                log.info(
                    f"[{module.name}] {model_seed.label}：已有 {count} 条，跳过（--refresh 可重填）"
                )
                continue
            _seed_model(
                model_seed, registry, stats, log, module.name, assets or {}, saved_files, pool
            )
    return stats


def run_config(
    config: SeedConfig, *, modules: list[str] | None, refresh: bool, log: RunLog
) -> SeedStats:
    """执行所选模块。版本 1 汇总模块失败，版本 2 遇错立即回滚。"""
    if config.version == 2 and refresh:
        raise SeedConfigError("version 2 使用业务键补齐数据，不支持 --refresh")
    selected = [m for m in config.modules if not modules or m.name in modules]
    if modules:
        unknown = set(modules) - {m.name for m in config.modules}
        if unknown:
            raise SeedConfigError(f"指定的模块在 YAML 中不存在：{sorted(unknown)}")
    if not selected:
        log.warning("无可执行模块（YAML 未声明业务数据或 --module 未匹配）")
        return SeedStats()

    total = SeedStats()
    pool = SeedImagePool()
    if config.version == 2:
        registry = SeedReferences(lookups=config.lookups)
        try:
            with _seed_transaction() as saved_files:
                for module in selected:
                    for seed in module.models:
                        _seed_model(
                            seed,
                            registry,
                            total,
                            log,
                            module.name,
                            config.assets,
                            saved_files,
                            pool,
                        )
        except SeedConfigError as exc:
            raise SeedConfigError(f"本次所选模块已全部回滚：{exc}") from exc
        return total

    failures: list[str] = []
    for module in selected:
        try:
            stats = seed_module(module, refresh=refresh, log=log, assets=config.assets, pool=pool)
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
