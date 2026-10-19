from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1394",
    "page_type": "人物简介列表页",
    "structure_group": "kunming_office_team_biography_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_office_team_biography_v1",
    "leader_region_selector": ".right .tab-bd .tab-pal",
    "name_selector": "班子成员段落开头至首个中文逗号",
    "duty_selector": "同一人物段落内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "second_tab_panel_person_biographies",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "panels": ".right .tab-bd .tab-pal",
            "member_panel_index": 1,
            "paragraphs": "p",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML已经直接包含班子成员简介及现任职务原句",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理排版空白，不改写人物或职务语义。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从班子成员面板逐段提取姓名和同段完整“现任……”原句。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    panels = soup.select(".right .tab-bd .tab-pal")
    if len(panels) < 2:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in panels[1].select("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"^([\u4e00-\u9fff·]{2,4})[，,]", text)
        evidence_match = re.search(r"现任[^。]*。", text)
        if not name_match or not evidence_match:
            continue

        name = name_match.group(1)
        evidence = evidence_match.group(0).removeprefix("现任").removesuffix("。").strip()
        evidence = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", evidence)
        evidence = re.sub(r"\s*([、，；：。])\s*", r"\1", evidence)
        if name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "第二个.tab-pal班子成员面板；段首姓名；同段完整现任句",
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
