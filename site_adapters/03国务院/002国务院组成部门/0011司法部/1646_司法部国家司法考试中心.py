from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


PAGE_RULE: dict[str, Any] = {
    "rule_id": "1646",
    "page_type": "职务分组名单页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".TRS_Editor",
    "parser_id": "custom_moj_exam_center_leaders_v2",
    "structure_group": "正文段落_机构职务冒号姓名",
    "confidence": "high",
    "risk_notes": "使用raw_http避免通用采集器误跟随无障碍工具脚本；选择不再嵌套同类节点的最内层正文，职务前缀以运行器注入机构的司法部后缀动态校验。",
}


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, Any]) -> list[dict[str, str]]:
    """解析正文中逐段列出的机构职务和姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    scopes = [
        node
        for node in soup.select(page_rule["leader_region_selector"])
        if node.select_one(page_rule["leader_region_selector"]) is None
    ]
    if len(scopes) != 1:
        raise RuntimeError(f"最内层领导正文数量异常：{len(scopes)}")

    organization = _compact_text(str(page_rule.get("organization", "")))
    short_organization = organization.removeprefix("司法部")
    if not short_organization:
        raise RuntimeError("运行器未注入有效机构名称")

    rows: list[dict[str, str]] = []
    for paragraph in scopes[0].select("p"):
        text = _compact_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<duty>[^：:]+)[：:](?P<name>[\u3400-\u9fff·]{2,6})", text)
        if match is None or not match.group("duty").startswith(short_organization):
            continue
        rows.append({"name": match.group("name"), "duty": match.group("duty"), "detail_url": ""})

    if not rows:
        raise RuntimeError("领导正文未解析到有效人物")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
