from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1551",
    "domain": "www.meescc.cn",
    "page_type": "人物列表完整页",
    "structure_group": "meescc_trs_leader_link_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_meescc_current_leaders_v1",
    "leader_region_selector": ".content .TRS_Editor",
    "name_selector": "p a[href]",
    "duty_selector": "p中姓名后的文本",
    "detail_link_selector": "p a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".content .TRS_Editor p"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_anchor",
        "detail_collector_type": "static_http",
        "detail_link_selector": "p a[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 20,
        "candidate_links": [],
    },
    "risk_flag": "人物段落与空段落交替出现，部分二字姓名含全角空格；仅处理含姓名链接的段落",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".content .TRS_Editor",
            "name_selector": "p a[href]",
            "duty_selector": "p中姓名后的文本",
            "detail_link_selector": "p a[href]",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": [".content .TRS_Editor p"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "当前HTML已静态直出姓名链接和职务文本"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online",
            "behavior_changed": True,
        },
    },
}


def clean_text(value: str) -> str:
    """确定性清理HTML排版空白及中文标点周边空格。"""
    text = re.sub(r"\s+", " ", (value or "").replace("\xa0", " ").replace("\u3000", " ")).strip()
    text = re.sub(r"\s+([，、；。])", r"\1", text)
    return re.sub(r"([，、；。])\s+", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按含姓名链接的人物段落DOM顺序抽取姓名、职务和详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = "strategy=custom_parse_page；leader=.content .TRS_Editor；item=p[a]；name=a[href]；duty=姓名后文本"

    for paragraph in soup.select(".content .TRS_Editor p"):
        link = paragraph.select_one("a[href]")
        if link is None:
            continue
        raw_name = clean_text(link.get_text(" ", strip=True))
        name = re.sub(r"\s+", "", raw_name)
        full_text = clean_text(paragraph.get_text(" ", strip=True))
        evidence = clean_text(full_text[len(raw_name):]) if full_text.startswith(raw_name) else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence or name in seen:
            continue
        href = str(link.get("href", "")).strip()
        detail_url = ""
        if href and not href.lower().startswith(("#", "javascript:", "mailto:")):
            candidate = urljoin(final_url, href)
            if candidate.rstrip("/") != final_url.rstrip("/"):
                detail_url = candidate
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": detail_url,
                "evidence": evidence,
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
