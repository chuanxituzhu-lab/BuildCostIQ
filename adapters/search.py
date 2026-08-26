"""Local-first evidence search for the user-facing workbench.

This adapter deliberately lives outside Core and the frozen P01-P08 gateway.
It indexes local metadata, locally generated recognition Markdown, and saved
business results.  It never calls an external provider and never presents an
inference as a fact.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


MAX_RESULTS = 30
MAX_SNIPPET = 300
_HIDDEN_KEYS = {"content_hash", "document_id", "source_id", "storage_path", "audit_log"}
_FIELD_LABELS = {
    "contract_no": "合同编号",
    "contract_subtotal": "合同计划小计",
    "baseline_total": "基线合计",
    "unit_price": "单价",
    "amount": "金额",
    "total_amount": "总金额",
    "pending_count": "待处理数量",
    "pending_item_count": "待组价数量",
    "finding_count": "问题数量",
    "item_count": "项目数量",
    "status": "状态",
    "title": "标题",
    "name": "名称",
    "version": "版本",
    "basis": "依据",
}
_DOMAIN_TERMS = (
    "工程量", "清单", "合同", "金额", "单价", "成本", "基线", "变更", "签证", "依据", "信息价", "市场价",
    "定额", "图纸", "结算", "审计", "投标", "招标", "中标", "工期", "付款", "税率", "计价", "预警", "证据",
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _terms(query: str) -> list[str]:
    normalized = _clean(query).lower()
    if not normalized:
        return []
    terms: list[str] = [normalized]
    domain_hits = [term for term in _DOMAIN_TERMS if term in normalized]
    if len(domain_hits) >= 2:
        terms.extend(domain_hits)
    elif len(normalized) <= 6:
        for token in re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}", normalized):
            if token not in terms:
                terms.append(token)
    return list(dict.fromkeys(sorted(terms, key=len, reverse=True)))


def _match_score(text: str, terms: list[str]) -> tuple[int, str | None]:
    haystack = _clean(text).lower()
    if not haystack or not terms:
        return 0, None
    exact = terms[0]
    if exact in haystack:
        return 100 + len(exact), exact
    candidate_terms = terms[1:]
    if len(candidate_terms) >= 2 and not all(term in haystack for term in candidate_terms):
        return 0, None
    hits = [(term, haystack.count(term)) for term in candidate_terms if term in haystack]
    if not hits:
        return 0, None
    return sum((len(term) * 4) + count for term, count in hits), max(hits, key=lambda item: len(item[0]))[0]


def _snippet(text: str, match: str | None) -> str:
    normalized = _clean(text)
    if not normalized:
        return "未提供可检索的本地文字内容。"
    if not match:
        return normalized[:MAX_SNIPPET] + ("…" if len(normalized) > MAX_SNIPPET else "")
    index = normalized.lower().find(match.lower())
    if index < 0:
        return normalized[:MAX_SNIPPET] + ("…" if len(normalized) > MAX_SNIPPET else "")
    start = max(0, index - 90)
    end = min(len(normalized), index + len(match) + 180)
    prefix = "…" if start else ""
    suffix = "…" if end < len(normalized) else ""
    return prefix + normalized[start:end] + suffix


def _read_text(reader: Callable[[str], bytes] | None, content_hash: Any) -> str:
    if reader is None or not content_hash:
        return ""
    try:
        raw = reader(str(content_hash))
    except (FileNotFoundError, KeyError, OSError, ValueError):
        return ""
    return raw.decode("utf-8-sig", errors="replace")


def _record_text(value: Any, key: str = "") -> str:
    if isinstance(value, Mapping):
        parts: list[str] = []
        for child_key, child_value in value.items():
            if str(child_key) in _HIDDEN_KEYS or any(part in str(child_key).lower() for part in ("hash", "storage", "document_id")):
                continue
            child_text = _record_text(child_value, str(child_key))
            if child_text:
                label = _FIELD_LABELS.get(str(child_key), str(child_key))
                parts.append(f"{label}：{child_text}")
        return "；".join(parts)
    if isinstance(value, list):
        parts = []
        for item in value[:20]:
            item_text = _record_text(item, key)
            if item_text:
                parts.append(item_text)
        return "；".join(parts)
    if isinstance(value, (str, int, float, bool)):
        return _clean(value)
    return ""


def _result(
    *,
    result_id: str,
    title: str,
    type_label: str,
    scope_label: str,
    category: str,
    archive_path: str,
    text: str,
    metadata_text: str,
    terms: list[str],
    provenance: dict[str, Any],
    source_id: str = "",
    openable: bool = False,
    derived: bool = False,
) -> dict[str, Any] | None:
    content_score, content_match = _match_score(text, terms)
    metadata_score, metadata_match = _match_score(metadata_text, terms)
    score = content_score + metadata_score // 2
    if not score:
        return None
    content_hit = bool(content_score)
    match = content_match or metadata_match
    return {
        "result_id": result_id,
        "title": title or "未命名资料",
        "type_label": type_label or "本地资料",
        "scope_label": scope_label,
        "category": category or "未分类",
        "archive_path": archive_path or "未记录归档位置",
        "snippet": _snippet(text if content_hit else metadata_text, match),
        "match_kind": "资料正文命中" if content_hit else "资料索引命中",
        "match_status": "supported" if content_hit else "related",
        "score": score,
        "source_id": source_id if openable else "",
        "openable": openable,
        "derived": derived,
        "storage_path": provenance.get("storage_path", "") if openable else "",
        "provenance": {
            "origin": provenance.get("origin", "本地资料"),
            "source_name": provenance.get("source_name", title),
            "archive_path": archive_path or "未记录归档位置",
            "recognition": provenance.get("recognition", "未识别"),
            "local_only": True,
            "external_sent": False,
            "is_inference": False,
        },
    }


def search_local_evidence(
    state: Mapping[str, Any],
    basis_items: list[Mapping[str, Any]],
    query: str,
    *,
    scope: str = "all",
    stage: str = "",
    category: str = "",
    source_reader: Callable[[str], bytes] | None = None,
    can_view_source: bool = False,
    can_view_basis: bool = False,
) -> dict[str, Any]:
    """Search local project evidence and return a UI-safe evidence packet."""
    normalized_query = _clean(query)
    if not normalized_query:
        return {
            "query": "",
            "scope": scope,
            "results": [],
            "total": 0,
            "searched": {"project_sources": 0, "external_basis": 0, "business_records": 0},
        }
    terms = _terms(normalized_query)
    results: list[dict[str, Any]] = []
    searched = {"project_sources": 0, "external_basis": 0, "business_records": 0}

    if scope in {"all", "project"}:
        for source in state.get("sources") or []:
            searched["project_sources"] += 1
            recognition = dict(source.get("recognition") or {})
            artifact = dict(recognition.get("artifact") or {})
            if stage and stage not in str(source.get("archive_area", "")) and stage not in str(source.get("archive_path", "")):
                continue
            source_category = recognition.get("category") or source.get("archive_category") or "未分类"
            if category and category not in {source_category, source.get("archive_category")}: 
                continue
            artifact_text = _read_text(source_reader, artifact.get("content_hash"))
            metadata_text = " ".join(
                str(source.get(key, "")) for key in (
                    "name", "kind", "archive_area", "archive_path", "archive_category", "status"
                )
            ) + " " + " ".join(str(recognition.get(key, "")) for key in ("category", "status", "message"))
            item = _result(
                result_id=f"project-source:{source.get('source_id', '')}",
                title=str(source.get("name", "未命名资料")),
                type_label=str(source.get("kind", "项目资料")),
                scope_label="项目资料库",
                category=str(source_category),
                archive_path=str(source.get("archive_path") or source.get("archive_area") or "项目资料库/待分类"),
                text=artifact_text or str(recognition.get("text_preview", "")),
                metadata_text=metadata_text,
                terms=terms,
                source_id=str(source.get("source_id", "")),
                openable=can_view_source,
                derived=bool(artifact_text),
                provenance={
                    "origin": "本地项目资料库",
                    "source_name": source.get("name", ""),
                    "storage_path": source.get("storage_path", ""),
                    "recognition": recognition.get("status", "未识别"),
                },
            )
            if item:
                results.append(item)

        stage_labels = {
            "contract": "P01 合同与招采依据",
            "boq": "P02 清单资料",
            "drawings": "P03 图纸资料",
            "baseline": "P04 零号台账",
            "cost_plan": "P05 成本计划",
            "changes": "P06 变更管理",
            "evidence": "P07 证据关联",
            "review": "P08 结算初审",
        }
        for stage_key, stage_value in state.items():
            if stage_key not in stage_labels or not isinstance(stage_value, Mapping):
                continue
            searched["business_records"] += 1
            label = stage_labels[stage_key]
            if stage and not stage_key.upper().startswith(stage.upper().replace("P", "")) and stage not in label:
                continue
            record = stage_value.get("result") if isinstance(stage_value.get("result"), Mapping) else stage_value
            text = label + " " + _record_text(record)
            item = _result(
                result_id=f"business-record:{stage_key}",
                title=label,
                type_label="已保存业务记录",
                scope_label="P01–P08 工作记录",
                category=label,
                archive_path=f"当前项目/{label}",
                text=text,
                metadata_text=label,
                terms=terms,
                provenance={"origin": "本地 P01–P08 工作记录", "source_name": label, "recognition": "业务记录"},
            )
            if item:
                results.append(item)

    if scope in {"all", "basis"} and can_view_basis:
        for basis in basis_items:
            searched["external_basis"] += 1
            recognition = dict(basis.get("recognition") or {})
            artifact = dict(recognition.get("artifact") or {})
            basis_category = str(basis.get("category_label") or basis.get("category") or "外部依据")
            if category and category not in {basis_category, basis.get("category")}: 
                continue
            artifact_text = _read_text(source_reader, artifact.get("content_hash"))
            metadata_text = " ".join(str(basis.get(key, "")) for key in (
                "name", "title", "description", "category", "category_label", "source_org", "source_url", "version", "region", "pricing_mode", "tax_mode"
            )) + " " + str(recognition.get("text_preview", ""))
            item = _result(
                result_id=f"external-basis:{basis.get('basis_id', '')}",
                title=str(basis.get("title") or basis.get("name") or "未命名依据"),
                type_label="外部依据文件",
                scope_label="外部依据库",
                category=basis_category,
                archive_path=str(basis.get("archive_path") or "外部依据库/未分类"),
                text=artifact_text or str(recognition.get("text_preview", "")),
                metadata_text=metadata_text,
                terms=terms,
                provenance={
                    "origin": "本地外部依据库",
                    "source_name": basis.get("title") or basis.get("name", ""),
                    "storage_path": basis.get("storage_path", ""),
                    "recognition": recognition.get("status", "未识别"),
                },
                source_id=str(basis.get("basis_id", "")),
                openable=can_view_basis,
                derived=bool(artifact_text),
            )
            if item:
                results.append(item)

    results.sort(key=lambda item: (item["score"], item["match_status"] == "supported"), reverse=True)
    for item in results:
        item.pop("score", None)
    return {
        "query": normalized_query,
        "scope": scope,
        "stage": stage,
        "category": category,
        "results": results[:MAX_RESULTS],
        "total": len(results),
        "searched": searched,
    }


def build_evidence_answer(search_packet: Mapping[str, Any]) -> dict[str, Any]:
    """Create a deliberately non-generative answer from search evidence."""
    results = list(search_packet.get("results") or [])
    claims = [
        {
            "status": item.get("match_status", "related"),
            "label": "资料原文命中" if item.get("match_status") == "supported" else "资料索引命中",
            "text": item.get("snippet", ""),
            "source": item.get("title", "未命名资料"),
            "archive_path": item.get("archive_path", "未记录归档位置"),
            "result_id": item.get("result_id", ""),
            "is_inference": False,
        }
        for item in results[:8]
    ]
    supported = [item for item in results if item.get("match_status") == "supported"]
    if not results:
        answer = "未找到足够的本地依据，系统不能对这个问题给出确定结论。请补充资料或换一个更具体的关键词。"
        uncertainties = ["当前没有可引用的本地资料或已保存业务记录。"]
    elif supported:
        answer = f"本地检索命中 {len(results)} 条资料，其中 {len(supported)} 条出现了问题关键词的正文或识别稿内容。下面只列出可回溯的证据摘要，不把推断当作事实。"
        uncertainties = []
        if len(supported) > 1:
            uncertainties.append("多份资料同时命中；版本、时间和效力未由系统自动裁决，请打开引用资料人工核对。")
    else:
        answer = "找到了相关资料索引，但没有命中可验证的正文或识别稿内容，不能据此形成确定结论。"
        uncertainties = ["当前命中主要来自文件名称、分类或归档信息，请打开原件或识别稿核对。"]
    return {
        "answer": answer,
        "answer_mode": "local_evidence_summary",
        "answer_policy": "仅基于当前本地项目资料、外部依据快照和已保存业务记录；未启用外部 AI。无依据时不回答，存在多份命中时不自动裁决。",
        "claims": claims,
        "uncertainties": uncertainties,
        "external_ai": {"enabled": False, "requires_explicit_consent": True, "sent": False},
    }
