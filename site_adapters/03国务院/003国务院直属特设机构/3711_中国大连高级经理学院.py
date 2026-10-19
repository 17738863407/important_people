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
    "rule_id": "3711",
    "page_type": "人物列表完整页",
    "structure_group": "sasac_academy_leader_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_sasac_academy_leader_paragraphs_v1",
    "leader_region_selector": ".gywm .bottom dl:first-of-type dd p",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "学院领导", "end_anchor": "主要职责", "include_selectors": [".gywm .bottom dl:first-of-type"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "每个段落为一个职务组，姓名可能换行或为顿号分隔多人名单",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_paragraph_colon_groups",
    "locator": {"css": {"group_selector": ".gywm .bottom dl:first-of-type dd p"}, "api": {"enabled": False, "reason": "原始HTML直接提供学院领导职务与姓名"}, "migration": {"source": "new_verified_online", "verified_status": "verified_current_online"}},
}


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_names(value: str) -> list[str]:
    names = [clean_text(item).replace(" ", "") for item in re.split(r"[、，,；;]", value)]
    return [name for name in names if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name)]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    heading = next((node for node in soup.select(".gywm .bottom dl dt") if clean_text(node.get_text(" ", strip=True)) == "学院领导"), None)
    if heading is None or not isinstance(heading.parent, Tag):
        return []
    rows: list[dict[str, str]] = []
    for paragraph in heading.parent.select("dd p"):
        text = clean_text(paragraph.get_text(" ", strip=True)).replace("：", ":", 1)
        if ":" not in text:
            continue
        duty, names_text = text.split(":", 1)
        duty = clean_text(duty).replace(" ", "")
        for name in parse_names(names_text):
            rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=academy_leaders；order=paragraph_then_name_list"})
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
