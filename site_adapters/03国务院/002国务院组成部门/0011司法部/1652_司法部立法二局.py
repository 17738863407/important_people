from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag


PAGE_RULE: dict[str, Any] = {
    "rule_id": "1652",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".left_list",
    "parser_id": "custom_moj_department_leaders_v2",
    "structure_group": "厅局领导标题_后继名单",
    "confidence": "high",
    "risk_notes": "使用raw_http避免通用采集器误跟随无障碍工具脚本；仅解析左侧信息容器中以“领导”结尾标题后的首个名单，并排除源码注释历史记录。",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, Any]) -> list[dict[str, str]]:
    """解析司法部厅局页面的领导名单。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(page_rule["leader_region_selector"])
    if scope is None:
        raise RuntimeError("未找到厅局信息容器")

    headings = [
        node
        for node in scope.select(".list_title")
        if _clean_text(node.get_text(" ", strip=True)).endswith("领导")
    ]
    if len(headings) != 1:
        raise RuntimeError(f"领导标题数量异常：{len(headings)}")

    leader_list = headings[0].find_next_sibling("ul")
    if not isinstance(leader_list, Tag):
        raise RuntimeError("领导标题后未找到名单")

    rows: list[dict[str, str]] = []
    for item in leader_list.select(":scope > li.oneList"):
        text = _clean_text(item.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<duty>[^：:]+)[：:](?P<names>.+)", text)
        if match is None:
            continue
        duty = re.sub(r"\s+", "", match.group("duty"))
        names = [re.sub(r"\s+", "", name) for name in re.split(r"[、，,；;]+", match.group("names"))]
        for name in names:
            if re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
                rows.append({"name": name, "duty": duty, "detail_url": ""})

    if not rows:
        raise RuntimeError("厅局领导名单未解析到有效人物")
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
