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
    "rule_id": "1299",
    "page_type": "人物目录详情页",
    "structure_group": "xinjiang_prison_directory_detail_fields",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_xinjiang_prison_directory_detail_fields_v1",
    "leader_region_selector": ".gknr_list",
    "name_selector": ".gknr_list dd a[title][href]",
    "duty_selector": "详情.gknbxq_detail职务字段",
    "detail_link_selector": ".gknr_list dd a[title][href]",
    "content_scope": {"start_anchor": "领导介绍", "end_anchor": "", "include_selectors": [".gknr_list dd a[title][href]", ".gknbxq_detail"], "exclude_selectors": ["发布时间", "头像", "页脚"]},
    "detail_strategy": {"required": True, "mode": "directory_details", "detail_collector_type": "static_http", "detail_link_selector": ".gknr_list dd a[title][href]", "detail_name_selector": ".gknbxq_detail姓名字段", "detail_duty_selector": ".gknbxq_detail职务字段", "detail_content_selector": ".gknbxq_detail", "max_detail_links": 50},
    "risk_flag": "详情正文含头像和重复姓名；只接受明确姓名/职务标签字段并与目录姓名核对",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".gknr_list", "name_selector": "dd a[title][href]", "duty_selector": "详情.gknbxq_detail职务字段", "detail_link_selector": "dd a[title][href]", "content_scope": {"start_anchor": "姓名字段", "end_anchor": "职务字段结束", "include_selectors": [".gknbxq_detail"], "exclude_selectors": ["头像", "重复标题"]}},
        "api": {"enabled": False, "reason": "当前静态HTML目录与详情字段直接提供姓名、职务和链接"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def _fetch_detail(url: str) -> tuple[str, str]:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _extract_fields(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".gknbxq_detail")
    if scope is None:
        return "", ""
    name = ""
    duty = ""
    for line in [_clean_text(value) for value in scope.get_text("\n", strip=True).splitlines()]:
        if re.match(r"^姓名[:：]", line):
            name = re.sub(r"^姓名[:：]\s*", "", line)
        elif re.match(r"^职务[:：]", line):
            duty = re.sub(r"^职务[:：]\s*", "", line)
    return re.sub(r"\s+", "", name), duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".gknr_list dd a[title][href]"):
        list_name = re.sub(r"\s+", "", _clean_text(link.get_text(" ", strip=True) or str(link.get("title", ""))))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", list_name) or list_name in seen:
            continue
        detail_html, detail_url = _fetch_detail(urljoin(base_url, str(link.get("href", ""))))
        name, duty = _extract_fields(detail_html)
        if name != list_name or not duty:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty, "parser": "custom_xinjiang_prison_directory_detail_fields_v1", "selector_summary": ".gknr_list目录；详情.gknbxq_detail姓名/职务字段"})
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
