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

def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".jgejy_con01 li > a[href]"):
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue
        if name in seen:
            continue
        seen.add(name)

        detail_url = urljoin(base_url, link.get("href", "")) if base_url else ""
        if not detail_url:
            continue
        detail_result = fetch_by_raw_requests(detail_url)
        detail_text = clean_text(BeautifulSoup(detail_result.html, "html.parser").get_text(" ", strip=True))
        current_match = re.search(r"现任[^。]*。", detail_text)
        if not current_match:
            continue
        evidence = clean_text(current_match.group(0))
        duty = evidence.removeprefix("现任").removesuffix("。").strip()
        duty = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", duty)
        duty = re.sub(r"\s*([、，；：])\s*", r"\1", duty)

        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(rule.get("parser", "")),
            }
        )

    return rows


def main(page_rule: dict) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(page_rule, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule = {
        "rule_id": "1552",
        "domain": "www.mem.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "mem_ministry_leader_home_list",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "list_direct",
        "collector": "static_http",
        "parser": "page_inline_mem_jgejy_leader_list_v3",
        "leader_region_selector": ".jgejy_con01 ul",
        "name_selector": ".jgejy_con01 li > a[href]",
        "duty_selector": "详情页现任[^。]*。",
        "detail_link_selector": ".jgejy_con01 li > a[href]",
        "content_scope": {
            "start_anchor": "领导信息",
            "end_anchor": "主要职责",
            "include_selectors": [".jgejy_con01 ul"],
            "exclude_selectors": ["script", "style", "iframe", ".jgejy_con02"],
        },
        "detail_strategy": {
            "required": False,
            "mode": "list_detail",
            "detail_collector_type": "static_http",
            "detail_link_selector": ".jgejy_con01 li > a[href]",
            "detail_parser": "",
            "detail_name_selector": "",
            "detail_duty_selector": "",
            "detail_content_selector": "",
            "max_detail_links": 0,
            "candidate_links": [],
        },
        "risk_flag": "旧脚本使用 div#page_body 全页低置信解析且实测输出为空；改为领导信息列表定向解析",
        "confidence": "high",
        "profile_reusable": "是",
        "profile_judgement": "网页画像通过_可用于应急管理部机构首页领导信息列表",
        "filter_policy": "strong_no_wordlist",
        
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".jgejy_con01 ul",
                "name_selector": ".jgejy_con01 li > a[href]",
                "duty_selector": "详情页现任[^。]*。",
                "detail_link_selector": ".jgejy_con01 li > a[href]",
                "content_scope": {
                    "start_anchor": "领导信息",
                    "end_anchor": "主要职责",
                    "include_selectors": [".jgejy_con01 ul"],
                    "exclude_selectors": ["script", "style", "iframe", ".jgejy_con02"],
                },
            },
            "api": {"enabled": False, "reason": "在线机构首页直出领导姓名和详情链接，职务从实时详情页现任句提取"},
            "migration": {
                "source": "online_list_detail_repair",
                "verified_status": "online_pending",
                "behavior_changed": True,
            },
        },
    }
    main(rule)
