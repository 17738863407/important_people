from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3708",
    "page_type": "人物列表完整页",
    "structure_group": "sasac_public_institution_leader_lines_v1",
    "reuse_scope": "sasac_subsite_verified_structure",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_sasac_public_institution_leader_lines_v1",
    "leader_region_selector": ".gywm .bottom dl:first-of-type dd p",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "中心领导",
        "end_anchor": "主要职责",
        "include_selectors": [".gywm .bottom dl:first-of-type"],
        "exclude_selectors": ["script", "style"],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "职务在换行处可能折行，须以中文冒号为边界合并职务，并保持网页原顺序",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_colon_bounded_lines",
    "locator": {
        "css": {"container_selector": ".gywm .bottom dl:first-of-type dd p"},
        "api": {"enabled": False, "reason": "原始HTML已直接提供中心领导职务与姓名"},
        "migration": {"source": "new_verified_online", "verified_status": "verified_current_online"},
    },
}


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def is_name(value: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", value.replace(" ", "")))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    heading = next(
        (node for node in soup.select(".gywm .bottom dl dt") if clean_text(node.get_text(" ", strip=True)) == "中心领导"),
        None,
    )
    if heading is None or not isinstance(heading.parent, Tag):
        return []
    paragraph = heading.parent.select_one("dd p")
    if paragraph is None:
        return []
    lines = [clean_text(item) for item in paragraph.get_text("\n", strip=True).splitlines() if clean_text(item)]
    rows: list[dict[str, str]] = []
    duty_parts: list[str] = []
    pending_duty = ""
    for line in lines:
        normalized = line.replace("：", ":", 1)
        if ":" in normalized:
            left, right = normalized.split(":", 1)
            duty_parts.append(left)
            pending_duty = clean_text("".join(duty_parts))
            duty_parts = []
            name = clean_text(right).replace(" ", "")
            if name and is_name(name):
                rows.append({"name": name, "duty": pending_duty, "detail_url": "", "source_text": pending_duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=center_leaders；order=source_lines"})
                pending_duty = ""
            continue
        name = line.replace(" ", "")
        if pending_duty and is_name(name):
            rows.append({"name": name, "duty": pending_duty, "detail_url": "", "source_text": pending_duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=center_leaders；order=source_lines"})
            pending_duty = ""
        else:
            duty_parts.append(line)
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
