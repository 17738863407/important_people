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


def clean_text(value: str) -> str:
    """清理正文排版空白。"""
    return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按合并正文中的姓名加现任片段提取人物，排除主持和分管职责。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#newContent")
    if container is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in container.select("p"):
        name_node = paragraph.find("strong")
        if name_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = re.search(r"现任(.+?)(?=[，,](?:主持|负责|分管)|。|$)", text)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or match is None or name in seen:
            continue
        duty = clean_text(match.group(1))
        if not duty:
            continue
        evidence = duty
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "evidence": evidence,
                "confidence": "high",
                "parser": "page_inline_qinghai_petition_profiles_v2",
                "selector_summary": "scope=#newContent；name=p strong；duty=同段现任片段至职责标记/句号；detail=none",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "3062",
    "page_type": "多人物详情合并页",
    "structure_group": "qinghai_petition_profile_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_qinghai_petition_profiles_v2",
    "leader_region_selector": "#newContent p:has(strong)",
    "name_selector": "p strong",
    "duty_selector": "同段现任片段",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["#newContent"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "raw_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#newContent p:has(strong)",
            "name_selector": "p strong",
            "duty_selector": "同段现任片段",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": ["#newContent"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "静态合并正文已提供姓名和现任字段"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online",
            "behavior_changed": True,
        },
    },
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
