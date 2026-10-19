from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
import urllib3
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3801", "domain": "www.baoding.gov.cn", "page_type": "人物导航转逐人详情页",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_to_detail",
    "collector": "static_http", "parser": "page_inline_baoding_government_detail_chain_v1",
    "leader_region_selector": ".title_namesz", "name_selector": ".title_namesz a[title]", "duty_selector": ".sj_szzcnr",
    "detail_link_selector": ".title_namesz a[href]", "content_scope": {"start_anchor": "领导之窗", "end_anchor": "", "include_selectors": [".title_namesz"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "person_name_link", "candidate_links": []},
    "risk_flag": "入口仅展示当前人物，须按侧栏原始顺序逐个访问详情页读取姓名和职务字段", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def fetch_fields(detail_url: str) -> tuple[str, str]:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session = requests.Session()
    session.trust_env = False
    response = session.get(detail_url, timeout=20, verify=False, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    region = soup.select_one(".sj_szzcnr")
    text = clean_text(region.get_text(" ", strip=True) if region else "")
    match = re.search(r"姓名[：:]\s*([\u4e00-\u9fff·]{2,5})\s*职务[：:]\s*(.+?)(?:\s+分工[：:]|$)", text)
    return (match.group(1), clean_text(match.group(2))) if match else ("", "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".title_namesz")
    if not region:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for link in region.select("a[href]"):
        expected_name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", expected_name):
            continue
        detail_url = urljoin(base_url, str(link.get("href", "")))
        try:
            name, duty = fetch_fields(detail_url)
        except requests.RequestException:
            continue
        if name != expected_name or not duty:
            continue
        if detail_url.rstrip("/") == base_url.rstrip("/"):
            detail_url = ""
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url, "confidence": "high", "parser": str(page_rule.get("parser", ""))})
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
