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
    "rule_id": "3287",
    "domain": "www.yzbzzx.agri.cn",
    "page_type": "人物列表完整页",
    "structure_group": "yzbzzx_current_leader_links",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "list_direct",
    "collector": "chrome_cdp",
    "parser": "page_inline_yzbzzx_current_leaders_v1",
    "leader_region_selector": ".leader-content",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "p a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".leader-content p a[href]"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_anchor",
        "detail_collector_type": "chrome_cdp",
        "detail_link_selector": "p a[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 20,
        "candidate_links": [],
    },
    "risk_flag": "普通HTTP返回403防护页；旧脚本硬编码人物结果，现改为Chrome渲染DOM动态抽取",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".leader-content",
            "name_selector": "",
            "duty_selector": "",
            "detail_link_selector": "p a[href]",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": [".leader-content p a[href]"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "经Chrome CDP核验，渲染DOM已提供姓名、职务和详情链接"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online_chrome_cdp",
            "behavior_changed": True,
        },
    },
}


def clean_text(value: str) -> str:
    """确定性清理HTML排版空白。"""
    return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ").replace("\u3000", " ")).strip()


def split_name_duty(value: str) -> tuple[str, str]:
    """按领导链接中姓名与职务之间的排版空白拆分。"""
    text = clean_text(value)
    match = re.fullmatch(r"([\u4e00-\u9fff·]{2,5})\s+(.+)", text)
    if not match:
        return "", ""
    return match.group(1), clean_text(match.group(2))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按中心领导链接DOM顺序抽取姓名、原始职务和详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = "strategy=custom_parse_page；leader=.leader-content；item=p a[href]"

    for link in soup.select(".leader-content p a[href]"):
        name, evidence = split_name_duty(link.get_text(" ", strip=True))
        if not name or not evidence or name in seen:
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
