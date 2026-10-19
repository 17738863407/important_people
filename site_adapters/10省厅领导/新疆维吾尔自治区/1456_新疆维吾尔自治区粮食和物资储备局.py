from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1456",
    "page_type": "机构页领导列表转人物详情页",
    "structure_group": "xinjiang_grain_organization_leader_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_xinjiang_grain_organization_leader_detail_v2",
    "leader_region_selector": ".p20 .ldxx_p, .p20 .ldxx_fjz",
    "name_selector": ".ldxx_p h3 a[href], .ldxx_fjz a[href]",
    "duty_selector": "人物详情页 .grjj-name span:first-child",
    "detail_link_selector": ".ldxx_p h3 a[href], .ldxx_fjz a[href]",
    "content_scope": {"start_anchor": "领导信息", "end_anchor": "组织机构图", "include_selectors": [".p20 .ldxx_p", ".p20 .ldxx_fjz"], "exclude_selectors": ["机构简介"]},
    "detail_strategy": {"required": True, "mode": "list_item_dynamic_link", "detail_collector_type": "requests", "detail_link_selector": ".ldxx_p h3 a[href], .ldxx_fjz a[href]", "detail_name_selector": ".grjj-name span:nth-child(2)", "detail_duty_selector": ".grjj-name span:first-child", "detail_content_selector": ".grjj-pic", "max_detail_links": 50},
    "risk_flag": "部分人物入口为jump中转页，必须动态跟随其中个人简历链接并以最终详情页字段为准",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".p20 .ldxx_p, .p20 .ldxx_fjz", "name_selector": ".ldxx_p h3 a[href], .ldxx_fjz a[href]", "detail_name_selector": ".grjj-name span:nth-child(2)", "detail_duty_selector": ".grjj-name span:first-child"},
        "api": {"enabled": False, "reason": "机构页和人物详情页均为静态HTML，按页面链接可复现抓取"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按机构页顺序访问每位领导详情页，并从独立字段提取姓名、职务。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    candidate_links = soup.select(".p20 .ldxx_p h3 a[href], .p20 .ldxx_fjz a[href]")

    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            )
        }
    )
    for candidate_link in candidate_links:
        candidate_url = urljoin(base_url, str(candidate_link.get("href", "")))
        try:
            response = session.get(candidate_url, timeout=30)
            response.raise_for_status()
            detail_soup = BeautifulSoup(response.content, "html.parser")

            resume_link = detail_soup.find(
                "a",
                href=True,
                string=lambda value: _clean_text(value or "") == "个人简历",
            )
            detail_url = response.url
            redirect_node = detail_soup.select_one("#url")
            if not detail_soup.select_one(".grjj-name") and (
                resume_link is not None or redirect_node is not None
            ):
                redirect_value = (
                    str(resume_link.get("href", ""))
                    if resume_link is not None
                    else _clean_text(redirect_node.get_text(" ", strip=True))
                )
                detail_url = urljoin(response.url, redirect_value)
                response = session.get(detail_url, timeout=30)
                response.raise_for_status()
                detail_soup = BeautifulSoup(response.content, "html.parser")
                detail_url = response.url
        except requests.RequestException:
            continue

        fields = detail_soup.select(".grjj-name span")
        if len(fields) < 2:
            continue
        duty = _clean_text(fields[0].get_text(" ", strip=True))
        raw_name = re.sub(r"\s+", "", _clean_text(fields[1].get_text(" ", strip=True)))
        name_match = re.match(r"[\u4e00-\u9fff·]{2,12}", raw_name)
        name = name_match.group(0) if name_match is not None else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,12}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_xinjiang_grain_organization_leader_detail_v2",
                "selector_summary": "机构页领导链接；中转页个人简历；详情页.grjj-name独立字段",
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
