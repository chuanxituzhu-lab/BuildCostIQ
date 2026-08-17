"""External-tool connector registry and portable project exchange contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO, StringIO
import csv
import json
from pathlib import PurePosixPath
from typing import Any, Mapping
from zipfile import ZIP_DEFLATED, ZipFile


@dataclass(frozen=True, slots=True)
class ConnectorDescriptor:
    id: str
    name: str
    category: str
    directions: tuple[str, ...]
    formats: tuple[str, ...]
    status: str
    description: str


CONNECTORS: tuple[ConnectorDescriptor, ...] = (
    ConnectorDescriptor(
        "excel-csv",
        "Excel / CSV",
        "office",
        ("import", "export"),
        (".xlsx", ".xlsm", ".csv"),
        "ready",
        "清单、价册和成本计划的双向表格交换。",
    ),
    ConnectorDescriptor(
        "word-report",
        "Word",
        "office",
        ("import", "export"),
        (".doc", ".docx", ".html"),
        "ready",
        "合同/说明资料归档与项目报告导出。",
    ),
    ConnectorDescriptor(
        "cad-quantity",
        "CAD / 算量",
        "engineering",
        ("import", "export"),
        (".dwg", ".dxf", ".xlsx", ".csv"),
        "exchange",
        "图纸和算量文件进入项目资料库，通过交换包共享标准化结果。",
    ),
    ConnectorDescriptor(
        "budget-software",
        "预算软件",
        "engineering",
        ("import", "export"),
        (".xlsx", ".csv", ".zip"),
        "exchange",
        "预算清单、价册和项目包的双向交换入口。",
    ),
    ConnectorDescriptor(
        "project-bundle",
        "BuildCostIQ 项目包",
        "exchange",
        ("import", "export"),
        (".zip", ".json", ".csv"),
        "ready",
        "携带项目状态、标准化数据、报告和原始资料的本地交换包。",
    ),
    ConnectorDescriptor(
        "government-basis",
        "政府政策/计价依据接口",
        "basis",
        ("import",),
        (".json", ".csv", ".pdf"),
        "consent",
        "按明确指令取得政策和计价文件的本地快照，不自动发送项目资料。",
    ),
    ConnectorDescriptor(
        "quota-basis",
        "定额接口",
        "basis",
        ("import",),
        (".json", ".csv", ".xlsx"),
        "consent",
        "取得定额、费用定额和编码换算数据后保存为本地版本快照。",
    ),
    ConnectorDescriptor(
        "price-information",
        "造价信息接口",
        "basis",
        ("import",),
        (".json", ".csv", ".xlsx"),
        "consent",
        "取得人材机信息价和地区价格，记录发布日期、有效期和适用区域。",
    ),
)


def connector_catalog() -> list[dict[str, Any]]:
    return [asdict(connector) for connector in CONNECTORS]


def _csv_bytes(headers: list[str], rows: list[list[object]]) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def build_project_bundle(state: Mapping[str, Any], source_reader) -> bytes:
    """Build a portable local exchange package without changing Core records."""
    project = dict(state["project"])
    boq = (state.get("boq") or {}).get("result") or {}
    plan = (state.get("cost_plan") or {}).get("result") or {}
    review = (state.get("review") or {}).get("result") or {}
    manifest = {
        "format": "buildcostiq-project-bundle",
        "version": 1,
        "project_id": project["id"],
        "project_name": project["name"],
        "artifacts": ["project.json", "boq.csv", "cost-plan.csv", "report.html"],
        "source_count": len(state.get("sources") or []),
        "derived_count": sum(1 for source in state.get("sources") or [] if (source.get("recognition") or {}).get("artifact")),
    }
    boq_rows = [
        [item.get("code"), item.get("name"), item.get("unit"), item.get("quantity")]
        for item in boq.get("items", [])
    ]
    plan_rows = [
        [item.get("code"), item.get("name"), item.get("unit"), item.get("quantity"), item.get("unit_price"), item.get("amount"), item.get("status")]
        for item in plan.get("items", [])
    ]
    report = (
        "<html><meta charset='utf-8'><body>"
        f"<h1>{project['name']} · BuildCostIQ 项目交换包</h1>"
        f"<p>清单项：{len(boq.get('items', []))}；成本计划项：{len(plan.get('items', []))}；初审：{'通过' if review.get('publishable') else '需处理'}</p>"
        "</body></html>"
    ).encode("utf-8")
    project_json = json.dumps(dict(state), ensure_ascii=False, indent=2, default=str).encode("utf-8")
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
        archive.writestr("project.json", project_json)
        archive.writestr("boq.csv", _csv_bytes(["项目编码", "项目名称", "单位", "工程量"], boq_rows))
        archive.writestr("cost-plan.csv", _csv_bytes(["项目编码", "项目名称", "单位", "工程量", "合同单价", "金额", "状态"], plan_rows))
        archive.writestr("report.html", report)
        for source in state.get("sources") or []:
            filename = PurePosixPath("sources") / PurePosixPath(str(source.get("name", "source.bin"))).name
            try:
                content = source_reader(source)
            except (FileNotFoundError, ValueError):
                continue
            archive.writestr(str(filename), content)
            artifact = (source.get("recognition") or {}).get("artifact") or {}
            artifact_hash = artifact.get("content_hash")
            if artifact_hash:
                try:
                    derived_content = source_reader(artifact)
                except (FileNotFoundError, ValueError):
                    continue
                derived_name = PurePosixPath("derived") / PurePosixPath(str(artifact.get("name", "source.md"))).name
                archive.writestr(str(derived_name), derived_content)
    return output.getvalue()
