from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
import urllib3
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3775",
    "domain": "www.huaian.gov.cn",
    "page_type": "人物导航转逐人详情页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_huaian_party_detail_chain_v1",
    "leader_region_selector": ".ldzc .right",
    "name_selector": ".wk5 a.ldzclista",
    "duty_selector": ".ziwu",
    "detail_link_selector": ".wk5 a.ldzclista[href]",
    "content_scope": {"start_anchor": "市　委", "end_anchor": "人　大", "include_selectors": [".ldzc .right"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "person_name_link", "candidate_links": []},
    "risk_flag": "入口为首位领导详情页；须仅取市委首个导航组并逐页读取职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理页面排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def fetch_duty(detail_url: str) -> str:
    """在线读取人物详情页中的明确职务字段。"""
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session = requests.Session()
    session.trust_env = False
    response = session.get(detail_url, timeout=20, verify=False, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    node = soup.select_one(".ldzc .mid .ziwu")
    return clean_text(node.get_text(" ", strip=True) if node else "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """保持市委导航顺序，动态访问每个人物详情页取得职务证据。"""
    soup = BeautifulSoup(html, "html.parser")
    right = soup.select_one(".ldzc .right")
    if not right:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    first_group = right.select_one(".wk5")
    if not first_group:
        return []
    rows: list[dict[str, str]] = []
    for link in first_group.select("a.ldzclista[href]"):
        name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue
        detail_url = urljoin(base_url, str(link.get("href", "")))
        try:
            duty = fetch_duty(detail_url)
        except requests.RequestException:
            duty = ""
        if not duty:
            continue
        if detail_url.rstrip("/") == base_url.rstrip("/"):
            detail_url = ""
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url, "confidence": "high", "parser": str(page_rule.get("parser", ""))})
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
