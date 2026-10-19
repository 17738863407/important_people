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


def normalize_space(text: str) -> str:
    """清理网页排版空白，不改变职务语义。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    """删除强结构姓名节点中的纯排版空白。"""
    return re.sub(r"\s+", "", normalize_space(text))


def build_page_rule(rule_id: str) -> dict:
    """构造当前页面经过在线核验的技术规则。"""
    return {
        "rule_id": rule_id,
        "domain": "www.dswxyjy.org.cn",
        "page_type": "职务姓名分栏列表",
        "structure_group": "people_daily_career_leader_name_rows_2026",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "career_and_linked_name_rows",
        "collector": "static_http",
        "parser": "page_dswxyjy_leader_rows_v1",
        "leader_region_selector": ".list.lingdao .contents",
        "name_selector": ".leader-name a[href]",
        "duty_selector": ".career",
        "detail_link_selector": ".leader-name a[href]",
        "content_scope": {
            "include_selectors": [".list.lingdao .contents"],
            "exclude_selectors": ["script", "style"],
        },
        "detail_strategy": {
            "required": False,
            "mode": "direct_person_link",
            "detail_link_selector": ".leader-name a[href]",
            "candidate_links": [],
        },
        "risk_flag": "verified_direct_rows",
        "confidence": "high",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".list.lingdao .contents",
                "item_selector": ":scope > div",
                "name_selector": ".leader-name a[href]",
                "duty_selector": ".career",
            },
            "api": {"enabled": False, "reason": "静态HTML逐行包含职务、姓名和独立详情链接"},
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按网页原始行序提取领导姓名、职务和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".list.lingdao .contents")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    for item in region.find_all("div", recursive=False):
        duty_node = item.select_one(".career")
        name_node = item.select_one(".leader-name a[href]")
        if duty_node is None or name_node is None:
            continue
        name = clean_name(name_node.get_text(" ", strip=True))
        duty = normalize_space(duty_node.get_text(" ", strip=True)).replace(" ", "").strip("：:，,。.；;")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, str(name_node.get("href", ""))),
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.list.lingdao .contents；row=>div；fields=.career+.leader-name a",
            }
        )
    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    page_rule = build_page_rule(rule_id)
    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(
        page_rule,
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=False,
    )
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "3595"
    main(rule_id_value)
