from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"\s+", "", normalize_space(text).lstrip("·"))


def clean_duty(text: str) -> str:
    duty = normalize_space(text)
    duty = re.sub(r"\s+([、，,）)])", r"\1", duty)
    duty = re.sub(r"([（(、，,])\s+", r"\1", duty)
    duty = re.sub(r"(?:（挂职）|\(挂职\)|[<＜]挂职[>＞])", "", duty)
    duty = re.sub(r"[，,、；;：:]\s*$", "", duty).strip()
    return duty.rstrip("。.")


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_name(text)))


def fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", errors="ignore")


def parse_detail_duty(detail_html: str, name: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    region = soup.select_one(".TRS_Editor") or soup
    text = normalize_space(region.get_text(" ", strip=True))
    match = re.search(rf"[【\[]\s*{re.escape(name)}\s*[：:]\s*(?P<duty>.+?)\s*[】\]]", text)
    if not match:
        return ""
    return clean_duty(match.group("duty"))


PAGE_RULE = {
        "rule_id": "1383",
        "domain": "kjt.jl.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_table_list_bounded_detail",
        "collector": "static_http",
        "parser": "page_jilin_science_leader_bounded_details_v1",
        "leader_region_selector": ".leader .module",
        "name_selector": ".leader_name",
        "duty_selector": ".leader_postion",
        "detail_link_selector": "",
        "content_scope": {
            "start_anchor": "",
            "end_anchor": "",
            "include_selectors": ["td.td14biaot a[href]"],
            "exclude_selectors": [],
        },
        "detail_strategy": {
            "required": True,
            "mode": "bounded_manual",
            "detail_collector_type": "static_http",
            "detail_link_selector": "td.td14biaot a[href]",
            "detail_parser": "detail_jilin_science_trs_editor_bracket_duty_v1",
            "detail_name_selector": "",
            "detail_duty_selector": ".TRS_Editor text in 【姓名：职务】",
            "detail_content_selector": ".TRS_Editor",
            "max_detail_links": 7,
        },
        "risk_flag": "bounded_detail_chain_7",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": "td.td14biaot a[href]",
                "name_selector": "td.td14biaot a",
                "duty_selector": "detail .TRS_Editor text in 【姓名：职务】",
                "detail_link_selector": "td.td14biaot a[href]",
                "content_scope": {
                    "start_anchor": "",
                    "end_anchor": "",
                    "include_selectors": ["td.td14biaot a[href]"],
                    "exclude_selectors": [],
                },
            },
            "api": {"enabled": False, "reason": "组织机构列表仅列姓名，职务位于对应领导详情页开头"},
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select(".leader .module"):
        meta = soup.select_one('meta[http-equiv="Refresh"], meta[http-equiv="refresh"]')
        refresh = re.search(
            r"url\s*=\s*([^\"'>\s]+)",
            str(meta.get("content", "")) if meta else "",
            re.IGNORECASE,
        )
        if refresh:
            final_url = urljoin(final_url, refresh.group(1))
            soup = BeautifulSoup(fetch_html(final_url), "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()

    modules = soup.select(".leader .module")
    if not modules:
        raise RuntimeError("当前在线领导页未发现人物模块")
    for module in modules:
        name_node = module.select_one(".leader_name")
        duty_node = module.select_one(".leader_postion")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_duty(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not is_name(name) or name in seen_names:
            continue
        if not duty or len(duty) > 120:
            continue

        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "入口META刷新；.leader .module内姓名和职务强字段",
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
