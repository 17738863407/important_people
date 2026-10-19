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
    "rule_id": "3791", "domain": "www.sxjz.gov.cn", "page_type": "同页四套班子领导列表",
    "load_mode": "浏览器渲染DOM", "fetch_mode": "online", "force_browser": True, "extract_mode": "list_direct",
    "collector": "browser_dom", "parser": "page_inline_jinzhong_people_congress_v1",
    "leader_region_selector": ".mBd", "name_selector": ".leaderList .title a", "duty_selector": ".leaderList .title .job",
    "detail_link_selector": ".leaderList .title a[href]", "content_scope": {"start_anchor": "人大领导", "end_anchor": "政府领导", "include_selectors": [".leaderList"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "同页四组领导名单，只取第二个人大列表", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    groups = soup.select(".mBd ul.leaderList")
    if len(groups) < 2:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for item in groups[1].select("li"):
        link = item.select_one(".title a[href]")
        duty_node = item.select_one(".title .job")
        if not link or not duty_node:
            continue
        name = re.sub(r"\s+", "", clean_text(next(link.stripped_strings, "")))
        duty = clean_text(duty_node.get_text(" ", strip=True)).rstrip(" ：:")
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
