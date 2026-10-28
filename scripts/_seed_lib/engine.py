"""数据填充引擎 —— 根据种子配置自动生成业务数据。

核心流程：
1. 加载 seeds/ 目录下的模块配置
2. 按依赖关系拓扑排序
3. 逐模块、逐模型生成数据并写入数据库
4. 每个模型在事务中执行，失败自动回滚

字段值生成策略由配置中的 type 决定，支持：
auto / username / name / text / title / choice / int / float /
datetime / bool / fk / image / const / email / phone / password
"""

import random
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any

from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone
from faker import Faker
from loguru import logger

fake = Faker("zh_CN")

# 全局已创建对象注册表：{ "app_label.ModelName": [instance, ...] }
_created_registry: dict[str, list] = defaultdict(list)
# round_robin 计数器
_rr_counters: dict[str, int] = defaultdict(int)


def reset_registry() -> None:
    """清空已创建对象注册表（每次完整 seed 流程开始前调用）。"""
    _created_registry.clear()
    _rr_counters.clear()


def get_model_class(model_path: str):
    """根据 'app_label.ModelName' 字符串获取 Django 模型类。"""
    try:
        return apps.get_model(model_path)
    except LookupError:
        logger.error("模型未找到: {}，请检查 seeds 配置中的 model 路径", model_path)
        raise


def _resolve_dependencies(modules: list[dict]) -> list[dict]:
    """拓扑排序：按 dependencies 确定模块执行顺序。

    Args:
        modules: 模块配置列表，每个包含 "name" 和 "dependencies" 键。

    Returns:
        排序后的模块列表（依赖在前，被依赖在后）。

    Raises:
        ValueError: 存在循环依赖时。
    """
    name_to_module = {m["name"]: m for m in modules}
    in_degree = defaultdict(int)
    graph = defaultdict(list)

    for m in modules:
        name = m["name"]
        if name not in in_degree:
            in_degree[name] = 0
        for dep in m.get("dependencies", []):
            graph[dep].append(name)
            in_degree[name] += 1

    # Kahn 算法
    queue = [n for n in name_to_module if in_degree[n] == 0]
    result = []
    while queue:
        node = queue.pop(0)
        result.append(name_to_module[node])
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(modules):
        missing = set(name_to_module) - {m["name"] for m in result}
        raise ValueError(f"循环依赖或引用缺失模块: {missing}")

    return result


def _generate_username() -> str:
    """生成拼音风格用户名。"""
    return fake.pystr(min_chars=4, max_chars=8).lower().replace(" ", "_")


def _generate_field_value(
    field_name: str,
    field_config: dict,
    model_class,
    instance_index: int,
    skip_images: bool,
    *,
    resolved_keywords: list[str] | None = None,
) -> object | None:
    """根据字段配置生成一个值。

    Args:
        field_name: 模型字段名。
        field_config: 字段配置字典（含 type 及其他附加参数）。
        model_class: Django 模型类。
        instance_index: 当前是第几个实例（从 0 开始）。
        skip_images: 是否跳过图片下载。

    Returns:
        生成的字段值；返回 _SKIP 表示跳过该字段（使用模型默认值或 auto）。
    """
    ftype = field_config.get("type", "auto")

    if ftype == "auto":
        return _SKIP

    if ftype == "const":
        return field_config.get("value")

    if ftype == "username":
        prefix = field_config.get("prefix", "user")
        return f"{prefix}_{instance_index + 1:03d}"

    if ftype == "name":
        return fake.name()

    if ftype == "email":
        return fake.email()

    if ftype == "phone":
        return fake.phone_number()

    if ftype == "password":
        # 返回明文密码，调用方需使用 make_password 或 create_user
        return field_config.get("value", "test123456")

    if ftype == "text":
        pool = field_config.get("pool", [])
        if pool:
            return random.choice(pool)
        # 根据 field_name 智能选择 faker 方法
        if "desc" in field_name or "描述" in field_name:
            return fake.paragraph(nb_sentences=3)
        if "content" in field_name or "内容" in field_name:
            return fake.paragraphs(nb=3, ext_word_list=None)
        if "title" in field_name or "标题" in field_name:
            return fake.sentence(nb_words=6)
        return fake.text(max_nb_chars=100)

    if ftype == "title":
        pool = field_config.get("pool", [])
        if pool:
            return random.choice(pool)
        return fake.sentence(nb_words=random.randint(3, 8))

    if ftype == "choice":
        choices = field_config.get("choices", [])
        if choices:
            return random.choice(choices)
        # 尝试从模型字段获取 choices
        try:
            model_field = model_class._meta.get_field(field_name)
            if hasattr(model_field, "choices") and model_field.choices:
                return random.choice(model_field.choices)[0]
        except Exception:
            pass
        return None

    if ftype == "int":
        min_val = field_config.get("min", 0)
        max_val = field_config.get("max", 1000)
        return random.randint(min_val, max_val)

    if ftype == "float":
        min_val = field_config.get("min", 0.0)
        max_val = field_config.get("max", 100.0)
        precision = field_config.get("precision", 2)
        return round(random.uniform(min_val, max_val), precision)

    if ftype == "datetime":
        days_back = field_config.get("days_back", 365)
        random_seconds = random.randint(0, days_back * 86400)
        return timezone.now() - timedelta(seconds=random_seconds)

    if ftype == "bool":
        true_rate = field_config.get("true_rate", 0.5)
        return random.random() < true_rate

    if ftype == "fk":
        return _resolve_fk(field_config, instance_index)

    if ftype == "image":
        if skip_images:
            return _SKIP
        return _resolve_image(field_config, instance_index, resolved_keywords=resolved_keywords)

    logger.warning("未知字段类型 '{}' (field={})", ftype, field_name)
    return _SKIP


def _resolve_fk(field_config: dict, instance_index: int) -> object | None:
    """解析外键字段值。"""
    ref_model_path = field_config.get("ref", "")
    strategy = field_config.get("strategy", "random")

    if not ref_model_path:
        logger.warning("fk 字段缺少 ref 配置")
        return None

    ref_model_class = get_model_class(ref_model_path)
    candidates = _created_registry.get(ref_model_path, [])

    if not candidates:
        # 尝试从数据库查询
        candidates = list(ref_model_class.objects.all()[:100])
        if not candidates:
            logger.warning("外键引用 '{}' 无可用记录", ref_model_path)
            return None

    if strategy == "random":
        return random.choice(candidates)
    if strategy == "first":
        return candidates[0]
    if strategy == "round_robin":
        idx = _rr_counters[ref_model_path] % len(candidates)
        _rr_counters[ref_model_path] += 1
        return candidates[idx]
    if strategy == "specific":
        filter_kwargs = field_config.get("filter", {})
        try:
            return ref_model_class.objects.filter(**filter_kwargs).first()
        except Exception as exc:
            logger.warning("fk specific 查询失败: {}", exc)
            return None
    if strategy == "cycle":
        # 轮询分配，每个外键目标关联大致相同数量的记录
        return candidates[instance_index % len(candidates)]

    logger.warning("未知 fk 策略 '{}', 回退 random", strategy)
    return random.choice(candidates)


def _resolve_fk_by_string(fk_field, value: str):
    """将行模板中的字符串值解析为外键模型实例。

    尝试顺序：
    1. 在已创建的注册表记录中按主键字段匹配
    2. 在已创建记录中按 name/title 字段匹配
    3. 在数据库中按 name/title 字段匹配
    """
    ref_model = fk_field.related_model
    ref_pk = ref_model._meta.pk.name if ref_model._meta.pk else "id"
    ref_path = f"{ref_model._meta.app_label}.{ref_model.__name__}"

    # 优先从已创建的注册表中查找
    candidates = _created_registry.get(ref_path, [])
    for obj in candidates:
        if str(getattr(obj, ref_pk, None)) == value:
            return obj
    for obj in candidates:
        for attr in ("name", "title", "username"):
            if hasattr(obj, attr) and getattr(obj, attr) == value:
                return obj

    # 回退到数据库查询
    for attr in ("name", "title", "username"):
        try:
            obj = ref_model.objects.filter(**{attr: value}).first()
            if obj:
                return obj
        except Exception:
            continue
    return None


def _resolve_image(
    field_config: dict, instance_index: int, *, resolved_keywords: list[str] | None = None
) -> object | None:
    """解析图片字段值（返回本地路径或 _SKIP）。

    Args:
        field_config: 图片字段配置。
        instance_index: 当前实例索引。
        resolved_keywords: 行模板解析后的关键词列表（优先使用）。
    """
    from utils.resource_fetcher import get_cached_image_path

    keywords = resolved_keywords or field_config.get("keywords", [])
    if not keywords:
        return _SKIP

    # 多关键词时按 instance_index 轮询
    keyword = keywords[instance_index % len(keywords)]
    # 同一关键词不同实例取不同图片
    img_index = instance_index // len(keywords)

    path = get_cached_image_path(keyword, index=img_index)
    if path:
        return _ImageValue(path=path, field_name=field_config.get("field", ""))
    return _SKIP


class _ImageValue:
    """图片值包装，延迟到对象创建后赋值。"""

    def __init__(self, path: Path, field_name: str) -> None:
        self.path = path
        self.field_name = field_name


class _SkipSentinel:
    """跳过字段赋值的哨兵值。"""

    def __repr__(self) -> str:
        return "<SKIP>"


_SKIP = _SkipSentinel()


class SeedEngine:
    """数据填充引擎。"""

    def __init__(self, *, skip_images: bool = False, dry_run: bool = False) -> None:
        self.skip_images = skip_images
        self.dry_run = dry_run
        self.stats: dict[str, dict] = {}

    def run_all(self, modules: list[dict]) -> dict:
        """按依赖顺序执行所有模块的填充。

        Returns:
            统计摘要字典 {module_name: {model: count, ...}, ...}。
        """
        sorted_modules = _resolve_dependencies(modules)
        logger.info("种子执行顺序: {}", " -> ".join(m["name"] for m in sorted_modules))

        for module in sorted_modules:
            self.run_module(module)

        return self.stats

    def run_module(self, module_config: dict) -> None:
        """执行单个模块的数据填充。"""
        module_name = module_config["name"]
        logger.info("=" * 60)
        logger.info("开始填充模块: {} ({})", module_name, module_config.get("description", ""))
        logger.info("=" * 60)

        module_stats = {}

        for model_config in module_config.get("models", []):
            model_path = model_config["model"]
            fields_config = model_config.get("fields", {})

            try:
                created = self._fill_model(model_path, model_config, fields_config)
                module_stats[model_path] = created
                logger.info("  {} 创建了 {} 条记录", model_path, created)

                # 图片后处理：按关联对象标题重新分配图片
                pp = model_config.get("post_process_images")
                if pp and not self.dry_run:
                    self._post_process_images(model_path, pp)
            except Exception as exc:
                logger.error("  {} 填充失败: {}", model_path, exc)
                module_stats[model_path] = f"FAILED: {exc}"

        self.stats[module_name] = module_stats

    def _fill_model(self, model_path: str, model_config: dict, fields_config: dict) -> int:
        """填充单个模型。支持两种模式：

        - rows 模式：model_config 含 'rows' 键时，每行作为模板生成一条记录，
          行内字段值与 fields_config 合并，行值优先。
        - generate 模式：按 fields_config 随机生成 count 条记录。
        """
        model_class = get_model_class(model_path)
        is_user_model = model_class == get_user_model()
        rows = model_config.get("rows")

        if rows is not None:
            return self._fill_model_rows(
                model_class, fields_config, rows, is_user_model, model_path
            )

        count = model_config.get("count", 10)
        created_count = 0
        for i in range(count):
            try:
                if self.dry_run:
                    logger.info("  [DRY-RUN] 将创建 {}.{} #{}", model_path, "instance", i + 1)
                    created_count += 1
                    continue

                obj = self._create_single_object(model_class, fields_config, i, is_user_model)
                if obj:
                    _created_registry[model_path].append(obj)
                    created_count += 1
            except Exception as exc:
                logger.warning("  创建 {}.{} #{} 失败: {}", model_path, "instance", i + 1, exc)
        return created_count

    def _fill_model_rows(
        self,
        model_class,
        base_fields: dict,
        rows: list[dict],
        is_user_model: bool,
        model_path: str,
    ) -> int:
        """行模板模式：每行生成一条记录，行内值优先于 base_fields。"""
        created_count = 0
        valid_field_names = {f.name for f in model_class._meta.get_fields()}

        for i, row in enumerate(rows):
            label = row.get("title") or row.get("name") or f"row#{i + 1}"
            try:
                if self.dry_run:
                    logger.info("  [DRY-RUN] 将创建 {}.{} ({})", model_path, "instance", label)
                    created_count += 1
                    continue

                # 合并字段配置：base + row 覆盖
                merged_fields = dict(base_fields)
                row_context: dict[str, Any] = {}
                for key, value in row.items():
                    if isinstance(value, dict) and "type" in value:
                        merged_fields[key] = value
                    else:
                        row_context[key] = value

                # 解析图片关键词引用（keywords_field 指向行内的关键词列表）
                resolved_kw: dict[str, list[str]] = {}
                for fname, fconfig in merged_fields.items():
                    if fconfig.get("type") == "image" and "keywords_field" in fconfig:
                        kw_field = fconfig["keywords_field"]
                        if kw_field in row_context:
                            resolved_kw[fname] = row_context[kw_field]

                # 生成字段值
                field_values = {}
                deferred_images: list[tuple[str, _ImageValue]] = []
                for field_name, fconfig in merged_fields.items():
                    if field_name in row_context and not isinstance(row_context[field_name], dict):
                        continue  # 行内直接赋值的字段，稍后统一处理
                    kw = resolved_kw.get(field_name)
                    value = _generate_field_value(
                        field_name,
                        fconfig,
                        model_class,
                        i,
                        self.skip_images,
                        resolved_keywords=kw,
                    )
                    if isinstance(value, _SkipSentinel):
                        continue
                    if isinstance(value, _ImageValue):
                        deferred_images.append((field_name, value))
                        continue
                    if value is not None:
                        field_values[field_name] = value

                # 行内直接赋值（含外键解析）
                for key, val in row_context.items():
                    if key not in valid_field_names or key in field_values:
                        continue
                    try:
                        field_obj = model_class._meta.get_field(key)
                    except Exception:
                        continue
                    if field_obj.is_relation and isinstance(val, str):
                        resolved = _resolve_fk_by_string(field_obj, val)
                        if resolved is not None:
                            field_values[key] = resolved
                        else:
                            logger.warning(
                                "  行 '{}' 的 {}='{}' 无法解析为外键记录，跳过",
                                label,
                                key,
                                val,
                            )
                    else:
                        field_values[key] = val

                # 创建对象
                if is_user_model:
                    username = field_values.pop("username", f"seed_user_{i}")
                    password = field_values.pop("password", "test123456")
                    email = field_values.pop("email", f"{username}@example.com")
                    obj = model_class.objects.create_user(
                        username=username, password=password, email=email, **field_values
                    )
                else:
                    obj = model_class(**field_values)
                    obj.save()

                # 延迟图片赋值
                for img_field_name, img_value in deferred_images:
                    from utils.resource_fetcher import assign_image_to_field

                    if assign_image_to_field(obj, img_field_name, img_value.path):
                        obj.save(update_fields=[img_field_name])

                _created_registry[model_path].append(obj)
                created_count += 1
            except Exception as exc:
                logger.warning("  创建 {}.{} ({}) 失败: {}", model_path, "instance", label, exc)

        return created_count

    def _post_process_images(self, model_path: str, config: dict) -> None:
        """图片后处理：按 FK 关联对象重新分配图片，使图片与业务主题匹配。

        通用能力，支持三种关键词解析策略（按优先级）：

        1. ``keywords_from_field`` — 从 FK 关联对象的指定字段读取关键词列表
           适用于：关联模型本身存储了关键词（如 Article.tag_list）
        2. ``title_keyword_map`` — 按 FK 关联对象的标题字段做模式匹配
           适用于：标题与图片主题存在明确映射关系（如商品名 → 搜索词）
        3. ``keywords`` — 所有实例使用固定关键词列表
           适用于：同一模型的所有图片共享主题（如公司 Logo）

        config 格式::

            {
                "fk_field": "article",              # 外键字段名
                "title_field": "headline",           # 可选，读取标题的字段名（默认自动检测 title/name）
                "keywords_from_field": "tags",       # 策略 1：从关联对象的 tags 字段读取关键词列表
                "title_keyword_map": {...},          # 策略 2：标题模式 → 关键词列表
                "keywords": ["default", "fallback"], # 策略 3：未匹配时的回退关键词
                "image_fields": ["image", "thumb"],  # 需要重新分配的图片字段列表
            }
        """
        from utils.resource_fetcher import assign_image_to_field, get_cached_image_path

        fk_field_name = config["fk_field"]
        title_field = config.get("title_field")
        keywords_from_field = config.get("keywords_from_field")
        title_keyword_map: dict[str, list[str]] = config.get("title_keyword_map", {})
        fallback_keywords: list[str] = config.get("keywords", [])
        image_fields: list[str] = config.get("image_fields", [])

        instances = _created_registry.get(model_path, [])
        if not instances:
            return

        reassigned = 0
        for instance in instances:
            related = getattr(instance, fk_field_name, None)
            if related is None:
                continue

            # ── 解析关键词 ──
            keywords = self._resolve_post_process_keywords(
                related,
                keywords_from_field=keywords_from_field,
                title_field=title_field,
                title_keyword_map=title_keyword_map,
                fallback_keywords=fallback_keywords,
            )
            if not keywords:
                continue

            # ── 重新分配图片 ──
            for field_name in image_fields:
                keyword = random.choice(keywords)
                img_index = random.randint(0, 4)
                path = get_cached_image_path(keyword, index=img_index)
                if path and assign_image_to_field(instance, field_name, path):
                    instance.save(update_fields=[field_name])
                    reassigned += 1

        logger.info("  {} 图片后处理: 重新分配了 {} 张图片", model_path, reassigned)

    @staticmethod
    def _resolve_post_process_keywords(
        related_obj,
        *,
        keywords_from_field: str | None = None,
        title_field: str | None = None,
        title_keyword_map: dict[str, list[str]] | None = None,
        fallback_keywords: list[str] | None = None,
    ) -> list[str] | None:
        """按策略优先级解析图片关键词。

        策略 1: keywords_from_field — 从关联对象指定字段读取
        策略 2: title_keyword_map   — 按标题模式匹配
        策略 3: fallback keywords   — 固定回退关键词
        """
        # 策略 1：从关联对象的字段直接读取关键词列表
        if keywords_from_field:
            value = getattr(related_obj, keywords_from_field, None)
            if isinstance(value, list) and value:
                return value
            if isinstance(value, str) and value:
                return [value]

        # 策略 2：标题模式匹配
        if title_keyword_map:
            text = ""
            if title_field:
                text = str(getattr(related_obj, title_field, "") or "")
            else:
                # 自动检测：优先 title → name → 第一个 CharField
                for attr in ("title", "name"):
                    text = str(getattr(related_obj, attr, "") or "")
                    if text:
                        break
                if not text:
                    for f in related_obj._meta.get_fields():
                        if getattr(f, "get_internal_type", lambda: "")() == "CharField":
                            text = str(getattr(related_obj, f.name, "") or "")
                            if text:
                                break
            if text:
                for pattern, kws in title_keyword_map.items():
                    if pattern in text:
                        return kws

        # 策略 3：固定回退关键词
        if fallback_keywords:
            return list(fallback_keywords)

        return None

    def _create_single_object(
        self, model_class, fields_config: dict, index: int, is_user_model: bool
    ):
        """创建单个模型实例（generate 模式）。"""
        field_values = {}
        deferred_images: list[tuple[str, _ImageValue]] = []

        for field_name, fconfig in fields_config.items():
            value = _generate_field_value(field_name, fconfig, model_class, index, self.skip_images)
            if isinstance(value, _SkipSentinel):
                continue
            if isinstance(value, _ImageValue):
                deferred_images.append((field_name, value))
                continue
            if value is not None:
                field_values[field_name] = value

        # User 模型使用 create_user
        if is_user_model:
            username = field_values.pop("username", f"seed_user_{index}")
            password = field_values.pop("password", "test123456")
            email = field_values.pop("email", f"{username}@example.com")
            obj = model_class.objects.create_user(
                username=username, password=password, email=email, **field_values
            )
        else:
            obj = model_class(**field_values)
            obj.save()

        # 处理延迟图片赋值
        for img_field_name, img_value in deferred_images:
            from utils.resource_fetcher import assign_image_to_field

            if assign_image_to_field(obj, img_field_name, img_value.path):
                obj.save(update_fields=[img_field_name])

        return obj


def run_seed(
    modules: list[dict],
    *,
    skip_images: bool = False,
    dry_run: bool = False,
    module_filter: str | None = None,
) -> dict:
    """一键执行种子数据填充。

    Args:
        modules: 所有模块配置列表。
        skip_images: 是否跳过图片下载。
        dry_run: 是否仅预览不执行。
        module_filter: 只执行指定模块（按 name 过滤）。

    Returns:
        统计摘要字典。
    """
    reset_registry()

    if module_filter:
        modules = [m for m in modules if m["name"] == module_filter]
        if not modules:
            logger.error(
                "未找到模块 '{}', 可用模块: {}", module_filter, [m["name"] for m in modules]
            )
            return {}

    engine = SeedEngine(skip_images=skip_images, dry_run=dry_run)

    start_time = time.time()
    stats = engine.run_all(modules)
    elapsed = time.time() - start_time

    logger.info("")
    logger.info("=" * 60)
    logger.info("种子填充完成！耗时 {:.1f}s", elapsed)
    logger.info("=" * 60)
    for mod_name, mod_stats in stats.items():
        logger.info("  模块 [{}]:", mod_name)
        for model_path, count in mod_stats.items():
            logger.info("    {} -> {}", model_path, count)

    return stats
