"""P08 —— 结算/清单初审（真实实现，替换原声明式占位）。

第一性原理：**清单初审里绝大多数问题是算术问题和一致性问题，不是理解问题。**
合价对不对、编码重不重、单位配不配、必填项缺不缺 —— 这些用确定性规则一次
扫描就能定死，答案唯一、可复现、可举证。只有"这个项目特征描述得对不对"
"这条组价合不合理"才轮得到模型。

本模块只做确定性的那一半，而且做到底：每条发现都带 ``rule_id`` 与
``evidence``（判定依据），可以直接落成 ``Evidence(kind="review_finding")``，
在审计场景里经得起对方问一句"你凭什么说这条有问题"。

三档严重度（block / warn / info）对应三种动作：
* ``block`` —— 算术或结构错误，事实层面站不住。有 block 就不允许发布。
* ``warn``  —— 存疑，需人工确认，不阻断。
* ``info``  —— 提示与覆盖度参考。

蒸馏来源与改造说明
------------------
规则清单与"发现对象"结构蒸馏自 MBSOFTCOM/cost-review 的 ``rule_engine.py``，
其"确定性规则与大模型分工"的切分是对的，值得吸收。以下为重写时的取舍：

* **金额一律 Decimal。** 原实现 ``check_total_equals_price_times_qty`` 用
  float 判定合价，而合价校验恰恰是浮点误差最致命的地方 —— 用 float 去证明
  "这个数不对"本身就不成立。本实现与 Core 既有 P05 保持同一套 Decimal 口径。
* **删除 ``qty > 100_000`` 魔数。** 原实现用一个与单位无关的固定阈值判"工程量
  偏大"，对市政道路（延米动辄十万级）会刷屏误报，对精装（个/套）又抓不住。
  改为调用方按单位注入上限（``quantity_ceilings``），没注入就不判 —— 宁可不
  报，不可乱报。
* **删除硬编码的 ``COMMON_DIVISION_CODES``。** 原实现内置 civil/install 两套
  分部模板，市政（04 章）根本不在其中。改为由调用方传入期望章节前缀。
* **删除字符集 Jaccard 匹配。** 原实现用 ``set(名称)`` 求交并比来匹配定额，
  忽略字序与字频，"钢筋混凝土管"和"混凝土钢管"会得到高分。价格偏离结论建立
  在这种匹配上是危险的。本实现只在调用方给出**明确的 code→参考价**映射时才
  判偏离，不做模糊匹配 —— 匹配是 P05 组价的职责，不是初审的职责。
* **新增口径闸门。** 原实现直接拿单价和信息价相减。本实现先过
  ``plugins.basis``：口径冲突则不出偏差数，只出一条 block。
* **新增单位一致性校验。** 原实现只在注释里提到"单位错配"，代码没实现。
  本实现接 ``plugins.normalize`` 真正比对清单单位与目录参考单位。
* 严重度由 red/yellow/blue 改为 block/warn/info —— 颜色是展示层概念，
  而本项目的边界规定 capability 只出结构化结果，不管展示。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from .basis import COMPARABLE, CONFLICTED, UNDECLARED, as_basis, comparable
from .normalize import UnitError, normalize_unit, unit_factor

__all__ = [
    "Finding",
    "SEVERITY_BLOCK",
    "SEVERITY_WARN",
    "SEVERITY_INFO",
    "review_boq",
    "SettlementReviewCapability",
]

SEVERITY_BLOCK = "block"
SEVERITY_WARN = "warn"
SEVERITY_INFO = "info"

# 合价校验容差：每行按 2 位小数舍入，单行舍入误差不超过 0.005，
# 取 0.02 留一倍余量；再大就不是舍入，是错误。
_AMOUNT_TOLERANCE = Decimal("0.02")

# GB 50500：9 位国标码 +（可选）3 位项目特征顺序码。
_CODE_LENGTHS = (9, 12)


@dataclass(frozen=True, slots=True)
class Finding:
    """一条审查发现。``evidence`` 是判定依据，不是复述结论。"""

    rule_id: str
    severity: str
    message: str
    evidence: str
    row: int | None = None
    code: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _Ctx:
    """一次审查所需的全部外部输入，全部可选 —— 没给就不判那一类。"""

    reference_units: Mapping[str, str] = field(default_factory=dict)
    reference_prices: Mapping[str, Any] = field(default_factory=dict)
    quantity_ceilings: Mapping[str, Any] = field(default_factory=dict)
    expected_divisions: Sequence[Any] = ()
    price_deviation_threshold: Decimal = Decimal("0.3")
    unit_aliases: Mapping[str, str] = field(default_factory=dict)


def _dec(value: object) -> Decimal | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        result = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


# ---------------------------------------------------------------- 行级规则

def _check_required(row: Mapping[str, Any], line: int | None) -> list[Finding]:
    labels = {"code": "项目编码", "name": "项目名称", "unit": "计量单位", "quantity": "工程量"}
    return [
        Finding(
            rule_id="R-FLD-01",
            severity=SEVERITY_WARN,
            message=f"{label}未填写",
            evidence="GB 50500 清单必填要素：编码 / 名称 / 特征 / 单位 / 工程量",
            row=line,
            code=_text(row.get("code")),
        )
        for key, label in labels.items()
        if not _text(row.get(key))
    ]


def _check_code_format(row: Mapping[str, Any], line: int | None) -> list[Finding]:
    code = _text(row.get("code"))
    if not code:
        return []  # 缺失由 R-FLD-01 覆盖，不重复报
    if not code.isdigit() or len(code) not in _CODE_LENGTHS:
        return [
            Finding(
                rule_id="R-CODE-01",
                severity=SEVERITY_WARN,
                message=f"清单编码格式不规范：{code!r}（应为 9 位或 12 位纯数字）",
                evidence="GB 50500：9 位国标码 + 3 位项目特征顺序码",
                row=line,
                code=code,
            )
        ]
    return []


def _check_quantity(row: Mapping[str, Any], line: int | None, ctx: _Ctx) -> list[Finding]:
    code = _text(row.get("code"))
    raw = row.get("quantity")
    quantity = _dec(raw)
    if quantity is None:
        if _text(raw):  # 有内容但不是数 —— 与"没填"是两回事
            return [
                Finding(
                    rule_id="R-QTY-02",
                    severity=SEVERITY_WARN,
                    message=f"工程量非数值：{raw!r}",
                    evidence="工程量单元格须为数值类型",
                    row=line,
                    code=code,
                )
            ]
        return []
    if quantity < 0:
        return [
            Finding(
                rule_id="R-QTY-01",
                severity=SEVERITY_BLOCK,
                message=f"工程量为负数：{quantity}",
                evidence="工程量为实体计量结果，不存在负值",
                row=line,
                code=code,
            )
        ]
    ceiling = _dec(ctx.quantity_ceilings.get(normalize_unit(row.get("unit"), ctx.unit_aliases)))
    if ceiling is not None and quantity > ceiling:
        return [
            Finding(
                rule_id="R-QTY-03",
                severity=SEVERITY_WARN,
                message=f"工程量 {quantity} 超出该单位约定上限 {ceiling}",
                evidence=f"调用方为单位 {normalize_unit(row.get('unit'), ctx.unit_aliases)!r} 设定的量级上限",
                row=line,
                code=code,
            )
        ]
    return []


def _check_amount(row: Mapping[str, Any], line: int | None) -> list[Finding]:
    """合价 = 单价 × 工程量。整个初审里唯一能给出确定性结论的算术闭环。"""
    quantity, price, total = _dec(row.get("quantity")), _dec(row.get("price")), _dec(row.get("total"))
    if quantity is None or price is None or total is None:
        return []
    expected = (quantity * price).quantize(Decimal("0.01"))
    if abs(expected - total) > _AMOUNT_TOLERANCE:
        return [
            Finding(
                rule_id="R-AMT-01",
                severity=SEVERITY_BLOCK,
                message=f"合价不符：单价 {price} × 工程量 {quantity} = {expected}，表中合价 {total}",
                evidence=f"合价 = 单价 × 工程量（容差 {_AMOUNT_TOLERANCE}）",
                row=line,
                code=_text(row.get("code")),
            )
        ]
    return []


def _check_unit(row: Mapping[str, Any], line: int | None, ctx: _Ctx) -> list[Finding]:
    """清单单位与目录参考单位比对。只在调用方注入了参考目录时生效。"""
    code = _text(row.get("code"))
    unit = _text(row.get("unit"))
    if not code or not unit or not ctx.reference_units:
        return []
    reference = ctx.reference_units.get(code) or ctx.reference_units.get(code[:9])
    if not reference:
        return []
    actual_norm = normalize_unit(unit, ctx.unit_aliases)
    reference_norm = normalize_unit(reference, ctx.unit_aliases)
    if actual_norm == reference_norm:
        return []
    try:
        factor = unit_factor(actual_norm, reference_norm, ctx.unit_aliases)
    except UnitError:
        return [
            Finding(
                rule_id="R-UNIT-01",
                severity=SEVERITY_BLOCK,
                message=f"计量单位与规范不符且不可换算：清单 {unit!r}，规范 {reference!r}",
                evidence=f"清单目录规定 {code} 的计量单位为 {reference!r}",
                row=line,
                code=code,
            )
        ]
    return [
        Finding(
            rule_id="R-UNIT-02",
            severity=SEVERITY_WARN,
            message=f"计量单位与规范存在 {factor} 倍差：清单 {unit!r}，规范 {reference!r}",
            evidence=f"清单目录规定 {code} 的计量单位为 {reference!r}；工程量须同步换算",
            row=line,
            code=code,
        )
    ]


def _check_price_deviation(row: Mapping[str, Any], line: int | None, ctx: _Ctx) -> list[Finding]:
    """单价偏离参考价。只按 code 精确取参考价，不做名称模糊匹配。"""
    code = _text(row.get("code"))
    price = _dec(row.get("price"))
    if not code or price is None or not ctx.reference_prices:
        return []
    reference = _dec(ctx.reference_prices.get(code))
    if reference is None or reference <= 0:
        return []
    deviation = (price - reference) / reference
    if abs(deviation) <= ctx.price_deviation_threshold:
        return []
    percent = (deviation * 100).quantize(Decimal("0.1"))
    return [
        Finding(
            rule_id="R-PRC-01",
            severity=SEVERITY_WARN,
            message=f"单价 {price} 偏离参考价 {reference}，偏离 {percent}%",
            evidence=f"参考价册 {code} = {reference}；阈值 ±{(ctx.price_deviation_threshold * 100).normalize()}%",
            row=line,
            code=code,
        )
    ]


# ---------------------------------------------------------------- 跨行规则

def _check_duplicates(rows: Sequence[Mapping[str, Any]]) -> list[Finding]:
    """重复编码。12 位重复是硬错，9 位重复只是提示（本就允许多条特征）。"""
    seen: dict[str, list[int | None]] = defaultdict(list)
    for index, row in enumerate(rows, start=1):
        code = _text(row.get("code"))
        if code:
            seen[code].append(row.get("row") if row.get("row") is not None else index)

    findings: list[Finding] = []
    for code, lines in seen.items():
        if len(lines) < 2 or len(code) != 12:
            continue
        findings.append(
            Finding(
                rule_id="R-CODE-02",
                severity=SEVERITY_BLOCK,
                message=f"12 位清单编码重复：{code} 出现 {len(lines)} 次（行 {lines}）",
                evidence="GB 50500：后 3 位为项目特征顺序码，同一工程内不得重复",
                row=lines[0],
                code=code,
            )
        )
    return findings


def _check_coverage(rows: Sequence[Mapping[str, Any]], ctx: _Ctx) -> list[Finding]:
    """漏项提示。期望章节由调用方按项目类型给出，本模块不内置模板。"""
    if not ctx.expected_divisions:
        return []
    present = {_text(row.get("code"))[:4] for row in rows if _text(row.get("code"))}
    findings: list[Finding] = []
    for entry in ctx.expected_divisions:
        prefix, label = (entry, entry) if isinstance(entry, str) else (entry[0], entry[1])
        if prefix not in present:
            findings.append(
                Finding(
                    rule_id="R-COV-01",
                    severity=SEVERITY_INFO,
                    message=f"未见 {label}（{prefix}）分部工程，请确认是否漏项",
                    evidence="调用方给定的本项目期望分部章节清单",
                    code=prefix,
                )
            )
    return findings


def _check_basis(ctx_basis: Any, reference_basis: Any) -> tuple[list[Finding], bool]:
    """口径闸门。返回（发现列表, 是否允许出价格偏差数）。"""
    left, right = as_basis(ctx_basis), as_basis(reference_basis)
    if left is None and right is None:
        return [], True  # 没有参考价册可比，价格规则本就不会触发
    status, reason = comparable(left, right)
    if status == COMPARABLE:
        note: list[Finding] = []
        if left and right and left.price_date != right.price_date:
            note.append(
                Finding(
                    rule_id="R-BAS-03",
                    severity=SEVERITY_INFO,
                    message=f"跨期比价：基准取价期 {left.price_date}，参考取价期 {right.price_date}",
                    evidence="两本价册取价期不同，偏差中含价格时间变动因素",
                )
            )
        return note, True
    if status == CONFLICTED:
        return [
            Finding(
                rule_id="R-BAS-01",
                severity=SEVERITY_BLOCK,
                message=reason,
                evidence="税制口径不同的两个单价不构成可比数量，相减无效",
            )
        ], False
    assert status == UNDECLARED
    return [
        Finding(
            rule_id="R-BAS-02",
            severity=SEVERITY_WARN,
            message=reason,
            evidence="价格口径须声明：税制 / 价格类型 / 出处 / 取价期",
        )
    ], False


# ---------------------------------------------------------------- 执行入口

def review_boq(
    rows: Sequence[Mapping[str, Any]],
    *,
    reference_units: Mapping[str, str] | None = None,
    reference_prices: Mapping[str, Any] | None = None,
    reference_basis: Any = None,
    subject_basis: Any = None,
    quantity_ceilings: Mapping[str, Any] | None = None,
    expected_divisions: Sequence[Any] = (),
    price_deviation_threshold: Any = "0.3",
    unit_aliases: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """对清单行执行全部确定性规则。

    每个参考输入都是可选的：**没给就不判那一类规则，绝不用默认值替代事实。**

    返回 ``{"findings": [...], "summary": {...}, "publishable": bool}``；
    ``publishable`` 为 False 表示存在 block 级发现，该版本不应对外发布。
    """
    threshold = _dec(price_deviation_threshold) or Decimal("0.3")
    ctx = _Ctx(
        reference_units=reference_units or {},
        reference_prices=reference_prices or {},
        quantity_ceilings=quantity_ceilings or {},
        expected_divisions=tuple(expected_divisions),
        price_deviation_threshold=threshold,
        unit_aliases=unit_aliases or {},
    )

    findings, price_rules_enabled = _check_basis(subject_basis, reference_basis)

    for index, row in enumerate(rows, start=1):
        line = row.get("row") if row.get("row") is not None else index
        findings.extend(_check_required(row, line))
        findings.extend(_check_code_format(row, line))
        findings.extend(_check_quantity(row, line, ctx))
        findings.extend(_check_amount(row, line))
        findings.extend(_check_unit(row, line, ctx))
        if price_rules_enabled:
            findings.extend(_check_price_deviation(row, line, ctx))

    findings.extend(_check_duplicates(rows))
    findings.extend(_check_coverage(rows, ctx))

    counts = {level: 0 for level in (SEVERITY_BLOCK, SEVERITY_WARN, SEVERITY_INFO)}
    for finding in findings:
        counts[finding.severity] += 1

    return {
        "findings": [finding.as_dict() for finding in findings],
        "summary": {
            "row_count": len(rows),
            "finding_count": len(findings),
            "price_rules_applied": price_rules_enabled,
            **counts,
        },
        "publishable": counts[SEVERITY_BLOCK] == 0,
    }


class SettlementReviewCapability:
    """P08 —— 结算/清单初审。

    Context keys:
        project_id (str, required)
        source_id  (str, required)
        rows       (list, optional) —— 待审清单行；缺省视为"尚无可审内容"
        reference_units   (dict, optional) —— {清单编码: 规范计量单位}
        reference_prices  (dict, optional) —— {清单编码: 参考单价}
        subject_basis     (dict, optional) —— 被审价册口径
        reference_basis   (dict, optional) —— 参考价册口径
        quantity_ceilings (dict, optional) —— {单位: 工程量上限}
        expected_divisions (list, optional) —— [(章节前缀, 名称), ...]
        price_deviation_threshold (str/num, optional) —— 默认 0.3
        unit_aliases (dict, optional) —— 地区定额私有单位写法

    每条 finding 可直接落为 ``Evidence(kind="review_finding")``。
    """

    capability_id = "P08"
    name = "settlement-review"

    def execute(self, context: Mapping[str, Any]) -> Mapping[str, Any]:
        missing = [key for key in ("project_id", "source_id") if not context.get(key)]
        if missing:
            raise ValueError(f"Missing context: {', '.join(missing)}")

        result = review_boq(
            context.get("rows") or [],
            reference_units=context.get("reference_units"),
            reference_prices=context.get("reference_prices"),
            reference_basis=context.get("reference_basis"),
            subject_basis=context.get("subject_basis"),
            quantity_ceilings=context.get("quantity_ceilings"),
            expected_divisions=context.get("expected_divisions") or (),
            price_deviation_threshold=context.get("price_deviation_threshold", "0.3"),
            unit_aliases=context.get("unit_aliases"),
        )

        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "project_id": context["project_id"],
            "source_id": context["source_id"],
            "status": "accepted",
            "findings": result["findings"],
            "summary": result["summary"],
            "publishable": result["publishable"],
        }
