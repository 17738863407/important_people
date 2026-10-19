from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0359",
    "page_type": "多人物详情合并页",
    "structure_group": "tianjin_finance_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_finance_leader_cards_v1",
    "leader_region_selector": ".ldxx-right-main",
    "name_selector": ".ldxx-zw",
    "duty_selector": ".ldxx-name",
    "detail_link_selector": "[onclick*='window.open']",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "",
        "include_selectors": [".ldxx-right-main"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "[onclick*='window.open']",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "旧字段映射颠倒；当前ldxx-zw为姓名、ldxx-name为完整现任职务",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".ldxx-right-main",
            "name_selector": ".ldxx-zw",
            "duty_selector": ".ldxx-name",
            "detail_link_selector": "[onclick*='window.open']",
            "content_scope": {
                "start_anchor": "领导信息",
                "end_anchor": "",
                "include_selectors": [".ldxx-right-main"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML领导卡片直接包含姓名、完整现任职务和详情页onclick",
        },
    },
}


def _clean_text(value: str) -> str:
    """清理排版空白，不删除“现任”或机构名称。"""
    return " ".join((value or "").replace("\u3000", " ").split())


def _parse_onclick_url(value: str, base_url: str) -> str:
    """从卡片onclick的window.open调用中提取动态详情链接。"""
    match = re.search(r"window\.open\(['\"](?P<url>[^'\"]+)", value or "")
    return urljoin(base_url, match.group("url")) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析领导卡片，继承首卡及后续列表的页面顺序。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", final_url))
    source_host = urlparse(source_url).netloc.lower()
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    cards = soup.select(".ldxx-right-main .ldxx-first, .ldxx-right-main ul.ldxx-second > li")
    for card in cards:
        name_node = card.select_one(".ldxx-zw")
        duty_node = card.select_one(".ldxx-name")
        if not name_node or not duty_node:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        duty = re.sub(r"^现任\s*", "", duty)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue

        detail_url = _parse_onclick_url(str(card.get("onclick") or ""), final_url or source_url)
        parsed = urlparse(detail_url)
        real_person_page = bool(
            re.fullmatch(r"/zwgk_53713/jggk/ldxx/[^/]+/\d{6}/t\d{8}_\d+\.html", parsed.path)
        )
        if parsed.netloc.lower() != source_host or not real_person_page:
            detail_url = ""

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_tianjin_finance_leader_cards_v1",
                "selector_summary": "ldxx-first及ldxx-second卡片；ldxx-zw姓名；ldxx-name完整职务",
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
