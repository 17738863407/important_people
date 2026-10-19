from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1397",
    "page_type": "职务分组名单页",
    "structure_group": "kunming_port_logistics_name_duty_colon_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_port_logistics_name_duty_colon_v1",
    "leader_region_selector": "#detail_con",
    "name_selector": "正文人物段落冒号前的段首姓名",
    "duty_selector": "段首姓名后至首个冒号前的原始职务",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "name_duty_colon_responsibility_same_paragraph",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#detail_con",
            "paragraphs": "p",
            "field_boundary": "first Chinese or ASCII colon",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML正文直接包含姓名、职务和分工段落",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析正文中“姓名 职务：分工”强边界段落。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("#detail_con") or soup
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in content.select("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,5})\s+(?P<duty>.+?)[：:]", text)
        if not match:
            continue
        name = match.group("name")
        duty = match.group("duty").strip(" ，,。；;")
        if not re.search(r"党组|书记|主任|成员|副主任", duty):
            continue
        if name in seen_names or len(duty) > 80:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "#detail_con人物段落；段首姓名；首个冒号前职务",
            }
        )
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
