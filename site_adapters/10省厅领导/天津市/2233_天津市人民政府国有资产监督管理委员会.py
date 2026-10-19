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
    "rule_id": "2233",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_sasac_two_committees_leaders",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_sasac_two_committees_leaders_v1",
    "leader_region_selector": "#BoxLeader .bd ul.leaderList首组",
    "name_selector": "a[href][title]",
    "duty_selector": ".job",
    "detail_link_selector": "a[href][title]",
    "content_scope": {
        "start_anchor": "两委领导",
        "end_anchor": "纪检监察组",
        "include_selectors": ["#BoxLeader .bd ul.leaderList首组"],
        "exclude_selectors": ["#BoxLeader .bd ul.leaderList次组"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "card_links",
        "detail_collector_type": "static_http",
        "detail_link_selector": "首组leaderList a[href][title]",
        "detail_name_selector": "title",
        "detail_duty_selector": ".job",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "页面含两委领导和纪检监察组两个Tab，后者重复段赛颖；仅解析.bd下首个leaderList",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#BoxLeader .bd ul.leaderList首组",
            "name_selector": "a[href][title]",
            "duty_selector": ".job",
            "detail_link_selector": "a[href][title]",
            "content_scope": {
                "start_anchor": "两委领导",
                "end_anchor": "纪检监察组",
                "include_selectors": ["#BoxLeader .bd ul.leaderList首组"],
                "exclude_selectors": ["#BoxLeader .bd ul.leaderList次组"],
            },
        },
        "api": {"enabled": False, "reason": "当前静态HTML首组领导列表直接提供姓名、职务和独立详情链接"},
    },
}


def _clean_text(value: str) -> str:
    """清理零宽字符、全角空格和排版空白。"""
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """仅按“两委领导”首组DOM顺序解析，排除第二Tab重复项。"""
    soup = BeautifulSoup(html, "html.parser")
    groups = soup.select("#BoxLeader .bd ul.leaderList")
    if not groups:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in groups[0].select(":scope > li"):
        link = item.select_one("a[href][title]")
        duty_node = item.select_one(".job")
        name = re.sub(r"\s+", "", _clean_text(str(link.get("title", "")))) if link else ""
        duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": urljoin(base_url, str(link.get("href", ""))),
            "evidence": duty,
            "parser": "custom_tianjin_sasac_two_committees_leaders_v1",
            "selector_summary": "#BoxLeader .bd首个leaderList；title姓名、.job职务、href详情",
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
