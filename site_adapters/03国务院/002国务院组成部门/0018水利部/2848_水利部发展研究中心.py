from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


PAGE_RULE: dict[str, Any] = {
    "rule_id": "2848",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".TRS_Editor",
    "parser_id": "custom_waterinfo_current_leaders_v2",
    "structure_group": "现任领导正文_姓名逗号职务逗号简历",
    "confidence": "high",
    "risk_notes": "选择不再嵌套同类节点的最内层正文，只接受姓名后的首段文本以注入机构名开头的人物段落。",
}


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, Any]) -> list[dict[str, str]]:
    """从现任领导正文段落动态提取姓名和网页原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    scopes = [
        node
        for node in soup.select(page_rule["leader_region_selector"])
        if node.select_one(page_rule["leader_region_selector"]) is None
    ]
    if len(scopes) != 1:
        raise RuntimeError(f"最内层现任领导正文数量异常：{len(scopes)}")

    organization = _compact_text(str(page_rule.get("organization", "")))
    if not organization:
        raise RuntimeError("运行器未注入机构名称")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in scopes[0].select("p"):
        text = _compact_text(paragraph.get_text(" ", strip=True))
        match = re.match(r"^(?P<name>[\u3400-\u9fff·]{2,20})[，,](?P<duty>[^，,。]+)", text)
        if match is None:
            continue

        name = match.group("name")
        duty = match.group("duty")
        if not duty.startswith(organization) or name in seen:
            continue

        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": ""})

    if not rows:
        raise RuntimeError("现任领导正文未解析到有效人物记录")
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
