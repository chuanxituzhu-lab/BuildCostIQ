"""价格口径（price basis）—— 一个价格在什么条件下才允许和另一个价格相减。

底层问题：**单价这个数字本身没有意义。** 有意义的是"某口径下的单价"。
含税价减除税价、2024 年一季度信息价减 2026 年市场询价、除税综合单价减
含税材料价 —— 这些减法在算术上全部成立，在造价上全部是错的，而且错得
安静：不报错、不越界、结果看着完全正常。

所以口径不是元数据，是**减法的前置条件**。本模块把这个前置条件变成代码
里的一道闸门：口径不清 → 只展示原始价，不出偏差数；口径冲突 → 拒绝相减
并说明理由。

蒸馏来源与改造说明
------------------
核心思想来自 BruceLee1024/cost-data 的 ``governance.py``（MIT）：该文件用
``price_warnings`` / ``comparability`` 把项目分成 searchable / restricted /
benchmark_candidate 三档，口径不全就降级为"可检索但不进入标杆样本池"。
这是整轮扫描里最有价值的一条工程判断。

改造：
* 原实现的口径是"项目级"的（挂在 ``Project.price_context`` 上）且和
  SQLAlchemy 模型耦合。这里下沉到**价格册级**（一本合同价册、一本市场价
  册各有自己的口径），因为同一项目里不同价册口径不同才是常态。
* 原实现只输出警告字符串，是否采信交给调用方。这里加了 ``comparable()``
  返回 ``(bool, reason)`` 的硬判定 —— 口径冲突时下游拿不到数，而不是拿到
  一个带警告的数。警告会被忽略，拿不到数不会。
* 增加 ``price_date``（取价期）。原实现没有时间维度，但信息价是按期发布
  的，跨期比价是造价审计里最常见的一类争议。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

__all__ = [
    "PriceBasis",
    "TAX_INCLUSIONS",
    "PRICE_TYPES",
    "UNDECLARED",
    "COMPARABLE",
    "CONFLICTED",
    "as_basis",
    "comparable",
]

# 税制口径 —— 这一项不一致，任何相减都无效。
TAX_INCLUSIONS = ("tax_inclusive", "tax_exclusive")  # 含税价 / 除税价

# 价格类型 —— 允许不一致（合同价 vs 市场价正是要比的），但必须声明。
PRICE_TYPES = (
    "winning_bid",        # 中标价（合同基准，唯一权威）
    "information_price",  # 造价站信息价
    "market_quote",       # 市场询价
    "quota_base",         # 定额基价
    "historical",         # 历史项目数据
)

UNDECLARED = "undeclared"   # 口径未声明：出数，但标记不可比
COMPARABLE = "comparable"   # 口径可比：允许相减
CONFLICTED = "conflicted"   # 口径冲突：拒绝相减


@dataclass(frozen=True, slots=True)
class PriceBasis:
    """一本价册的口径声明。四个字段全部必填才算声明完整。"""

    tax_inclusion: str      # TAX_INCLUSIONS 之一
    price_type: str         # PRICE_TYPES 之一
    source: str             # 出处：合同编号 / 信息价期号 / 询价单号
    price_date: str = ""    # 取价期，ISO 日期或期号（如 "2026-Q1"）

    def missing(self) -> tuple[str, ...]:
        """列出缺失或取值非法的字段。"""
        gaps: list[str] = []
        if self.tax_inclusion not in TAX_INCLUSIONS:
            gaps.append("tax_inclusion")
        if self.price_type not in PRICE_TYPES:
            gaps.append("price_type")
        if not str(self.source).strip():
            gaps.append("source")
        if not str(self.price_date).strip():
            gaps.append("price_date")
        return tuple(gaps)

    @property
    def declared(self) -> bool:
        return not self.missing()

    def as_dict(self) -> dict[str, str]:
        return {
            "tax_inclusion": self.tax_inclusion,
            "price_type": self.price_type,
            "source": self.source,
            "price_date": self.price_date,
        }


def as_basis(value: PriceBasis | Mapping[str, Any] | None) -> PriceBasis | None:
    """把调用方传来的 dict / PriceBasis / None 收敛成 PriceBasis | None。"""
    if value is None:
        return None
    if isinstance(value, PriceBasis):
        return value
    if isinstance(value, Mapping):
        return PriceBasis(
            tax_inclusion=str(value.get("tax_inclusion", "")).strip(),
            price_type=str(value.get("price_type", "")).strip(),
            source=str(value.get("source", "")).strip(),
            price_date=str(value.get("price_date", "")).strip(),
        )
    raise TypeError(f"无法解析为价格口径: {value!r}")


def comparable(left: PriceBasis | None, right: PriceBasis | None) -> tuple[str, str]:
    """判定两本价册能否相减。

    返回 ``(状态, 理由)``：

    * ``(COMPARABLE, "")``     —— 口径一致，允许出偏差数。
    * ``(CONFLICTED, 理由)``   —— 税制不一致，**拒绝**出偏差数。
    * ``(UNDECLARED, 理由)``   —— 有一方未声明完整，出数但标记不可比。

    注意"未声明"和"冲突"必须分开：前者是没说，后者是说了且相反。没说
    还有补救余地（补声明即可复算），说了且相反则这两个数根本不该相减。
    """
    if left is None or right is None:
        return UNDECLARED, "价格口径未提供：只展示原始价，偏差数不作为结论使用"

    left_gaps, right_gaps = left.missing(), right.missing()
    if left_gaps or right_gaps:
        detail = []
        if left_gaps:
            detail.append(f"基准价册缺 {'、'.join(left_gaps)}")
        if right_gaps:
            detail.append(f"对比价册缺 {'、'.join(right_gaps)}")
        return UNDECLARED, f"价格口径声明不完整（{'；'.join(detail)}）：偏差数不作为结论使用"

    if left.tax_inclusion != right.tax_inclusion:
        return CONFLICTED, (
            f"税制口径冲突（基准 {left.tax_inclusion} vs 对比 {right.tax_inclusion}）："
            f"两者不可相减，请先统一到同一税制后重算"
        )

    if left.price_date != right.price_date:
        return COMPARABLE, ""  # 跨期可比，但由 P08 出一条提示，不在此处拦截
    return COMPARABLE, ""
