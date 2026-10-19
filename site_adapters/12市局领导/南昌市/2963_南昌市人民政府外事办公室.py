from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2963",
    "page_type": "人物列表完整页",
    "structure_group": "nanchang_foreign_affairs_profile_paragraph_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online",
    "parser": "page_nanchang_foreign_affairs_profile_paragraph_v2",
    "leader_region_selector": ".content",
    "name_selector": ".content p人物简介段开头冒号前姓名",
    "duty_selector": ".content p人物简介段内机构全称起至负责或协助分工前",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "requests_without_browser_headers_may_return_403",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".content", "row_selector": ".content p"},
        "api": {"enabled": False, "reason": "当前HTTPS正文直接包含按版面顺序排列的人物简介段"},
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白，不改写原文标点或机构名称。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物简介段DOM顺序提取姓名及分工语句之前的完整原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".content")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,8})\s*[:：]\s*[男女]", text)
        duty_match = re.search(
            r"(?P<duty>南昌市人民政府外事办公室[（(]港澳事务办公室[）)][^，。]+)"
            r"(?=，(?:负责|协助)|。|$)",
            text,
        )
        if name_match is None or duty_match is None:
            continue
        name = name_match.group("name")
        evidence = normalize_space(duty_match.group("duty"))
        if name in seen or not evidence:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".content p按DOM顺序；段首冒号前姓名；机构全称起至负责或协助分工前为完整原始职务",
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
