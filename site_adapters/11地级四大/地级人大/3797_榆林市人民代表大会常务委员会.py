from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3797", "domain": "www.yl.gov.cn", "page_type": "同页四套班子标签列表",
    "load_mode": "浏览器渲染DOM", "fetch_mode": "online", "force_browser": True,
    "extract_mode": "list_direct", "collector": "browser_dom", "parser": "page_inline_yulin_people_congress_v1",
    "leader_region_selector": ".tab-item", "name_selector": "a.leader-item .name", "duty_selector": "a.leader-item .post",
    "detail_link_selector": "a.leader-item[href]", "content_scope": {"start_anchor": "市人大常委会", "end_anchor": "市政府", "include_selectors": [".tab-item"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "按明确人大标签或标题确认目标面板；当前页面仅公开市政府领导时必须失败，禁止按面板索引混入市政府名单", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    panels = soup.select(".tab-item")
    tabs = soup.select(".leader-tab-head a")
    target = None
    if len(tabs) == len(panels):
        target = next((panels[i] for i, tab in enumerate(tabs) if "人大" in tab.get_text()), None)
    title = soup.select_one(".gov-title")
    if target is None and len(panels) == 1 and title is not None and "人大" in title.get_text():
        target = panels[0]
    if target is None:
        raise RuntimeError("当前领导之窗未公开可确认的市人大常委会领导面板；不得采集市政府领导代替")
    if target.has_attr("hidden") or target.get("aria-hidden") == "true" or re.search(r"display\s*:\s*none", str(target.get("style", "")), re.I):
        raise RuntimeError("人大领导面板当前明确隐藏，需核验可见来源")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for link in target.select("a.leader-item[href]"):
        name_node = link.select_one(".name")
        duty_node = link.select_one(".post")
        if not name_node or not duty_node:
            continue
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True)))
        duty = clean_text(duty_node.get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, str(link.get("href", ""))), "confidence": "high", "parser": str(page_rule.get("parser", ""))})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
