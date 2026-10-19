from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2798",
    "page_type": "人物简介合集页",
    "structure_group": "lanzhou_veterans_zoom_profile_current_sentences_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_veterans_zoom_profile_current_sentences_v1",
    "leader_region_selector": "#zoom",
    "name_selector": "#zoom p人物简介段首个逗号前姓名",
    "duty_selector": "#zoom p当前人物简介段内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "historical_script_hardcoded_names_and_current_page_has_new_person",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom",
            "person_paragraph_selector": "#zoom p",
        },
        "api": {
            "enabled": False,
            "reason": "当前在线#zoom按DOM顺序直出5个人物简介段，每段均含姓名和完整现任句",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白及中文标点两侧空格。"""
    cleaned = re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", cleaned)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按#zoom人物简介段顺序动态提取姓名和完整现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#zoom")
    if container is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in container.find_all("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        name_match = re.match(
            r"(?P<name>[\u4e00-\u9fff·\s]{2,12})，(?:男|女)，",
            text,
        )
        current_match = re.search(r"现任[^。]{2,240}。", text)
        if not name_match or not current_match:
            continue
        name = re.sub(r"\s+", "", name_match.group("name"))
        evidence = re.sub(r"^现任\s*", "", normalize_space(current_match.group(0))).rstrip("。")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "#zoom人物简介p按DOM顺序；段首姓名并且同段存在完整现任句",
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
