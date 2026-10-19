from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0606",
    "page_type": "人物表格页",
    "structure_group": "changchun_police_name_province_city_duty_lines_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_police_name_province_city_duty_lines_v1",
    "leader_region_selector": "div.TRS_Editor div.Custom_UnionStyle div div",
    "name_selector": "行首至首个省/市职务边界",
    "duty_selector": "行内首个省/市起的原始职务",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["div.TRS_Editor div.Custom_UnionStyle"],
        "exclude_selectors": ["iframe"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "姓名和职务含全角及排版空格，人物行之间另有空节点",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_name_before_province_city_duty",
    "locator": {
        "css": {
            "leader_region_selector": "div.TRS_Editor div.Custom_UnionStyle div div",
            "name_selector": "line_prefix_before_first_province_or_city",
            "duty_selector": "line_suffix_from_first_province_or_city",
        },
        "api": {
            "enabled": False,
            "reason": "静态正文人物行已直接包含姓名和完整原始职务",
        },
        "migration": {
            "source": "legacy_inline_line_parser",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


LINE_PATTERN = re.compile(r"^(?P<name>.+?)\s*(?P<duty>[省市].+)$")
NAME_PATTERN = re.compile(r"[\u4e00-\u9fff·]{2,6}")
DUTY_HINT_PATTERN = re.compile(r"公安|党委|局长|主任|书记|委员|专员|组长|警长")


def clean_text(text: str) -> str:
    """清理全角空格及中文文字间的排版空白，不改变语义。"""
    normalized = " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())
    normalized = re.sub(r"\s*([、，,；;：:])\s*", r"\1", normalized)
    return re.sub(r"(?<=[\u4e00-\u9fff、，])\s+(?=[\u4e00-\u9fff])", "", normalized)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文行顺序从首个省/市职务边界拆分姓名和职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for node in soup.select(page_rule["leader_region_selector"]):
        line = clean_text(node.get_text(" ", strip=True))
        match = LINE_PATTERN.fullmatch(line)
        if match is None:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        evidence = clean_text(match.group("duty"))
        if (
            NAME_PATTERN.fullmatch(name) is None
            or DUTY_HINT_PATTERN.search(evidence) is None
            or name in seen
        ):
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "source_text": evidence,
                "method": page_rule["parser"],
                "note": (
                    "strategy=custom_parse_page；scope=TRS_Editor_Custom_UnionStyle_lines；"
                    "name=before_first_province_or_city；duty=from_first_province_or_city；"
                    "empty_nodes_and_iframes=excluded"
                ),
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
