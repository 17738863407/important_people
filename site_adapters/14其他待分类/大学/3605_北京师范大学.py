from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3605", "domain": "www.bnu.edu.cn", "page_type": "学校领导职务分组卡片",
    "structure_group": "bnu_leader_rows_2026", "reuse_scope": "single_page", "load_mode": "静态HTML直出",
    "fetch_mode": "online", "extract_mode": "grouped_leader_cards_merge", "collector": "static_http",
    "parser": "page_bnu_current_leaders_v1", "leader_region_selector": ".articleList03.articleList02",
    "name_selector": ".leader_row .leader-txt01", "duty_selector": ".leader_row .leader_title",
    "detail_link_selector": ".leader_row li a[href]", "detail_strategy": {"required": False, "mode": "direct_person_link", "candidate_links": []},
    "risk_flag": "merge_party_and_administrative_duties", "confidence": "high", "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean(text: str) -> str:
    """删除姓名和职务中的纯排版空白。"""
    return re.sub(r"\s+", "", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip("：:")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按职务分组顺序抽取，并按人物首次出现顺序合并多项职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".articleList03.articleList02")
    if region is None: return []
    store: dict[str, dict[str, object]] = {}
    for group in region.select(".leader_row"):
        duty_node = group.select_one(".leader_title")
        duty = clean(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not duty: continue
        for link in group.select(".leader_list01 li a[href]"):
            name_node = link.select_one(".leader-txt01")
            name = clean(name_node.get_text(" ", strip=True) if name_node else "")
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name): continue
            row = store.setdefault(name, {"duties": [], "detail_url": urljoin(final_url, str(link.get("href", "")))})
            if duty not in row["duties"]: row["duties"].append(duty)
    return [{"name": name, "duty": "；".join(data["duties"]), "evidence": "；".join(data["duties"]),
             "detail_url": str(data["detail_url"]), "parser": str(page_rule.get("parser", "")),
             "selector_summary": "strategy=custom_parse_page；region=.articleList03.articleList02；group=.leader_row；fields=.leader_title+.leader-txt01；duties=merged"}
            for name, data in store.items()]


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(PAGE_RULE, globals(), runtime_context=runtime_context, update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
