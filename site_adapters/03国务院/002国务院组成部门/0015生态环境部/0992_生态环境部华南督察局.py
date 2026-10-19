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
    "rule_id": "0992",
    "domain": "hndc.mee.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "mee_hndc_leader_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_mee_hndc_current_leaders_v1",
    "leader_region_selector": ".ldzc_box",
    "name_selector": "p strong",
    "duty_selector": "p中冒号前文本",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".ldzc_box p"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
        "candidate_links": [],
    },
    "risk_flag": "姓名和职务内部含半角及不换行排版空格；页面不提供人物详情链接",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".ldzc_box",
            "name_selector": "p strong",
            "duty_selector": "p中冒号前文本",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": [".ldzc_box p"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "当前原始HTML已静态直出职务和姓名段落"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online",
            "behavior_changed": True,
        },
    },
}


def compact_text(value: str) -> str:
    """移除姓名与职务内部仅用于排版的空白。"""
    return re.sub(r"\s+", "", (value or "").replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导段落DOM顺序抽取姓名与完整“职务：姓名”依据。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = "strategy=custom_parse_page；leader=.ldzc_box；item=p；name=strong；duty=冒号前文本"

    for paragraph in soup.select(".ldzc_box p"):
        name_node = paragraph.select_one("strong")
        name = compact_text(name_node.get_text(" ", strip=True) if name_node else "")
        text = paragraph.get_text(" ", strip=True)
        duty = compact_text(re.split(r"[：:]", text, maxsplit=1)[0] if re.search(r"[：:]", text) else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": selector_summary,
            }
        )
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
