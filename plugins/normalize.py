"""单位归一与换算 —— 清单/定额口径对齐的最底层设施。

问题的底层是什么：一条清单的"工程量"只有连上"单位"才有意义。造价现场
的单位写法是脏的（㎡ / m² / 平方米 / 平米 全是同一个东西），而定额的
计量单位又常带倍率（10m3、100m2、100m）。两者不归一就直接比价、直接
乘算，会产生 **静默的百倍误差** —— 数字看着正常，结果是错的。

所以本模块只做两件事，且只做这两件事：

1. ``normalize_unit``  把任意写法折叠成规范符号（m2 / m3 / t / m / 个 …）。
2. ``unit_factor``     求 source→target 的倍率（100m3 → m3 = 100）。

纯函数，无 IO，无数据库，无外部依赖。

蒸馏来源与改造说明
------------------
本模块的问题定义与别名表来自 BruceLee1024/cost-data 的
``normalization.py`` / ``unit_conversion.py``（MIT）。原实现把归一逻辑和
SQLAlchemy Session 焊死在一起：``normalize_unit(value, session)`` 要查
数据库表才能拿到规则，``conversion_factor`` 直接 ``select(UnitConversion)``。
那是应用层的写法，不是内核的写法。

改造：
* 剥离 Session —— 归一是纯计算，不该依赖持久层。自定义规则通过 ``extra``
  参数注入，调用方想从哪里取都行（JSON、数据库、配置），本模块不关心。
* 倍率从"内置 3 条 + 查表"改为"显式前缀解析"—— 定额单位的倍率是有构造
  规律的（``\\d+`` + 基本单位），解析比穷举表更完备，也不会漏。
* 增加 ``units_comparable``：真正的用途不是换算，而是**拦截**。两个不可
  换算的单位（m2 vs m3）碰在一起时，正确动作是报错，不是硬算。
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal
from typing import Mapping

__all__ = [
    "UNIT_ALIASES",
    "UnitError",
    "normalize_text",
    "normalize_unit",
    "split_unit_multiplier",
    "unit_factor",
    "units_comparable",
]


class UnitError(ValueError):
    """单位无法归一或两个单位之间不存在换算关系。"""


# 规范符号一律用 ASCII 小写，避免全角/半角/上标混入。
UNIT_ALIASES: dict[str, str] = {
    # 面积
    "㎡": "m2", "m²": "m2", "平方米": "m2", "平米": "m2", "平方": "m2", "sqm": "m2",
    # 体积
    "m³": "m3", "立方米": "m3", "立方": "m3", "方": "m3", "cbm": "m3",
    # 长度
    "米": "m", "延米": "m", "延长米": "m", "m": "m",
    "千米": "km", "公里": "km",
    "毫米": "mm", "厘米": "cm",
    # 质量
    "吨": "t", "公吨": "t", "t": "t",
    "千克": "kg", "公斤": "kg", "kg": "kg",
    # 计数
    "个": "个", "只": "个", "件": "个",
    "台": "台", "套": "套", "组": "组", "处": "处", "座": "座",
    "根": "根", "块": "块", "樘": "樘", "副": "副", "对": "对",
    "系统": "系统", "项": "项", "站": "站",
    # 工时/台班
    "工日": "工日", "台班": "台班",
}

# 同量纲分组：只有同组的单位之间才谈得上换算。
_DIMENSIONS: dict[str, str] = {
    "mm": "length", "cm": "length", "m": "length", "km": "length",
    "m2": "area",
    "m3": "volume",
    "kg": "mass", "t": "mass",
}

# 组内换算到基准单位的倍率。
_TO_BASE: dict[str, Decimal] = {
    "mm": Decimal("0.001"), "cm": Decimal("0.01"), "m": Decimal("1"), "km": Decimal("1000"),
    "m2": Decimal("1"),
    "m3": Decimal("1"),
    "kg": Decimal("1"), "t": Decimal("1000"),
}

# 定额单位前缀倍率：10m3 / 100m2 / 1000块 …
_MULTIPLIER_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*(.+)$")


def normalize_text(value: object | None) -> str:
    """全角折半角、去空白与常见分隔符、转小写。"""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    return re.sub(r"[\s·•,，;；:：()（）\[\]【】]+", " ", text).strip()


def normalize_unit(value: object | None, extra: Mapping[str, str] | None = None) -> str:
    """把任意单位写法折叠成规范符号；未知写法原样返回（不猜、不丢）。

    ``extra`` 是调用方注入的额外别名（地区定额的私有写法），优先于内置表。
    """
    raw = normalize_text(value).replace(" ", "")
    if not raw:
        return ""
    if extra and raw in extra:
        return extra[raw]
    if raw in UNIT_ALIASES:
        return UNIT_ALIASES[raw]
    # 带倍率前缀的单位：先剥前缀再归一，倍率保留在原串里由 unit_factor 处理。
    matched = _MULTIPLIER_PATTERN.match(raw)
    if matched:
        base = normalize_unit(matched.group(2), extra)
        if base:
            return f"{_canonical_number(matched.group(1))}{base}"
    return raw


def _canonical_number(text: str) -> str:
    """``"100"`` → ``"100"``；``"10.0"`` → ``"10"``。只在有小数点时去尾零。"""
    value = Decimal(text)
    return str(value.quantize(Decimal("1")) if value == value.to_integral_value() else value.normalize())


def split_unit_multiplier(unit: str, extra: Mapping[str, str] | None = None) -> tuple[Decimal, str]:
    """拆出倍率与基本单位：``"100m3"`` → ``(Decimal("100"), "m3")``。"""
    normalized = normalize_unit(unit, extra)
    if not normalized:
        return Decimal("1"), ""
    matched = _MULTIPLIER_PATTERN.match(normalized)
    if not matched:
        return Decimal("1"), normalized
    return Decimal(matched.group(1)), matched.group(2)


def units_comparable(source: str, target: str, extra: Mapping[str, str] | None = None) -> bool:
    """两个单位是否存在换算关系（同量纲，或归一后完全相同）。"""
    try:
        unit_factor(source, target, extra)
    except UnitError:
        return False
    return True


def unit_factor(source: str, target: str, extra: Mapping[str, str] | None = None) -> Decimal:
    """求 ``source`` → ``target`` 的倍率；不可换算时抛 ``UnitError``。

    ``unit_factor("100m3", "m3") == Decimal("100")``
    ``unit_factor("t", "kg")     == Decimal("1000")``
    ``unit_factor("m2", "m3")``  → UnitError
    """
    src_mult, src_base = split_unit_multiplier(source, extra)
    tgt_mult, tgt_base = split_unit_multiplier(target, extra)
    if not src_base or not tgt_base:
        raise UnitError(f"单位为空，无法换算: {source!r} → {target!r}")

    if src_base == tgt_base:
        return src_mult / tgt_mult

    src_dim, tgt_dim = _DIMENSIONS.get(src_base), _DIMENSIONS.get(tgt_base)
    if src_dim is None or tgt_dim is None or src_dim != tgt_dim:
        # 计数单位（个/台/套）之间没有换算关系，这是事实，不是缺陷。
        raise UnitError(f"单位不可换算: {source!r} → {target!r}")
    return (src_mult * _TO_BASE[src_base]) / (tgt_mult * _TO_BASE[tgt_base])
