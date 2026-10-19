from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3148",
    "page_type": "人物目录详情页",
    "structure_group": "yunnan_fao_leader_directory_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_yunnan_fao_leader_directory_details_v2",
    "leader_region_selector": ".member_listview a[href]",
    "name_selector": ".t",
    "duty_selector": "详情.panel中姓名与时间后的连续职务行",
    "detail_link_selector": ".member_listview a[href]",
    "content_scope": {
        "start_anchor": "领导成员首张目录卡片",
        "end_anchor": "领导成员末张目录卡片",
        "include_selectors": [".member_listview a[href]"],
        "exclude_selectors": ["新闻人物", "正文推荐", "二维码", "页脚"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "custom_parse_page",
        "detail_collector_type": "requests",
        "detail_link_selector": ".member_listview a[href]",
        "detail_name_selector": ".panel",
        "detail_duty_selector": ".panel中姓名与时间后的连续职务行",
        "detail_content_selector": ".panel",
        "max_detail_links": 20,
    },
    "risk_flag": "详情中职务后紧跟主持、分管、负责和简历；仅保留姓名与时间后的连续职务行，不添加机构前缀",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".member_listview a[href]",
            "name_selector": ".t",
            "duty_selector": "详情.panel中姓名与时间后的连续职务行",
            "detail_link_selector": ".member_listview a[href]",
            "content_scope": {
                "start_anchor": "领导成员首张目录卡片",
                "end_anchor": "领导成员末张目录卡片",
                "include_selectors": [".member_listview a[href]"],
                "exclude_selectors": ["新闻人物", "正文推荐", "二维码", "页脚"],
            },
        },
        "api": {"enabled": False, "reason": "静态目录与详情HTML直接提供姓名、职务和人物链接"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        if "member_listview" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def _extract_detail_duty(html: str, name: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    panel = soup.select_one(".panel")
    if panel is None:
        return ""
    lines = [_clean_text(line) for line in panel.get_text("\n", strip=True).splitlines()]
    lines = [line for line in lines if line]
    for index, line in enumerate(lines):
        if re.sub(r"\s+", "", line) != name or index + 1 >= len(lines):
            continue
        if not lines[index + 1].startswith("时间"):
            continue
        duty_parts: list[str] = []
        for candidate in lines[index + 2 :]:
            if candidate.startswith(("主持", "分管", "负责", "简历", "扫一扫")):
                break
            duty_parts.append(candidate)
        return " ".join(duty_parts).strip(" ：:，,。.；;")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".member_listview a[href]"):
        if _is_hidden(link):
            continue
        name_node = link.select_one(".t")
        raw_name = name_node.get_text(" ", strip=True) if name_node else link.get_text(" ", strip=True)
        name = re.sub(r"\s+", "", _clean_text(raw_name).replace("查看详情", ""))
        href = str(link.get("href") or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name) or not href or name in seen:
            continue
        detail_url = urljoin(final_url, href)
        detail_result = fetch_by_raw_requests(detail_url)
        duty = _extract_detail_duty(detail_result.html, name)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_result.final_url,
                "evidence": duty,
                "parser": "custom_yunnan_fao_leader_directory_details_v2",
                "selector_summary": ".member_listview目录姓名链接；详情.panel姓名/时间后连续职务行",
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
