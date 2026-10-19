from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1813",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_ethnic_religious_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_ethnic_religious_leader_cards_v1",
    "leader_region_selector": ".comm-list-leader ul.list",
    "name_selector": "li.listItem .name",
    "duty_selector": "li.listItem .zhiwei",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "",
        "include_selectors": [".comm-list-leader ul.list"],
        "exclude_selectors": ["工作分工区域", "个人简历区域"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "同卡包含工作分工和个人简历；仅解析.name和.zhiwei强字段，禁止整卡取证",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".comm-list-leader ul.list li.listItem",
            "name_selector": ".name",
            "duty_selector": ".zhiwei",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "领导信息",
                "end_anchor": "",
                "include_selectors": [".comm-list-leader ul.list"],
                "exclude_selectors": ["工作分工区域", "个人简历区域"],
            },
        },
        "api": {"enabled": False, "reason": "当前静态HTML领导卡片直接包含姓名和职务强字段"},
    },
}


def _clean_text(value: str) -> str:
    """清理零宽字符、全角空格和排版空白。"""
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def _clean_standalone_concurrent_marker(value: str) -> str:
    """删除独立“兼”状态标记，保留具体兼任职务。"""
    return re.sub(r"(?:（兼）|\(兼\)|[<＜]兼[>＞])", "", _clean_text(value)).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导卡片DOM顺序读取姓名和职务强字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(".comm-list-leader ul.list li.listItem"):
        name_node = item.select_one(".name")
        duty_node = item.select_one(".zhiwei")
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True))) if name_node else ""
        duty = _clean_standalone_concurrent_marker(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": "",
            "evidence": duty,
            "parser": "custom_tianjin_ethnic_religious_leader_cards_v1",
            "selector_summary": ".comm-list-leader li.listItem；name=.name；duty=.zhiwei",
        })
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
