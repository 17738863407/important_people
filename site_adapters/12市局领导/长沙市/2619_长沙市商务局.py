from __future__ import annotations

import re
import sys
from urllib.parse import urljoin
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "2619", "page_type": "人物目录详情页",
    "structure_group": "changsha_commerce_detail_labeled_dl", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "directory_detail",
    "collector": "static_http", "parser": "changsha_commerce_detail_labeled_dl_v2",
    "leader_region_selector": "a[href*='/ldxx/']", "name_selector": "h2.leader-tit",
    "duty_selector": ".wrap_right dl", "detail_link_selector": "a[href]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
    "risk_flag": "按目录顺序在线解析详情独立职务dl，排除工作分工和简历",
    "confidence": "high", "profile_reusable": "", "profile_judgement": "",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _extract_detail_fields(detail_html: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    name_node = soup.select_one("h2.leader-tit")
    if name_node is None:
        return "", ""
    name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True)))
    duties: list[str] = []
    for field in soup.select(".wrap_right dl"):
        label = field.select_one("h2")
        if label is None or re.sub(r"\s+", "", label.get_text()) != "职务":
            continue
        full_text = _clean_text(field.get_text(" ", strip=True))
        duty = _clean_text(full_text[len(_clean_text(label.get_text(" ", strip=True))):])
        if duty:
            duties.append(duty)
    if not re.fullmatch(r"[一-鿿·]{2,8}", name) or len(duties) != 1:
        return "", ""
    return name, duties[0]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    from crawler_core.fetcher import fetch_by_raw_requests
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    rows: list[object] = []
    seen: set[str] = set()
    for link in soup.select(page_rule["leader_region_selector"]):
        name = _clean_text(link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(link.get("href", "" )).strip())
        if not re.fullmatch(r"[一-鿿·]{2,8}", name):
            continue
        if name in seen:
            raise RuntimeError(f"目录姓名重复：{name}")
        detail_result = fetch_by_raw_requests(detail_url, timeout=60)
        detail_name, duty = _extract_detail_fields(detail_result.html)
        if detail_name != name or not duty:
            raise RuntimeError(f"详情姓名职务异常：目录={name}，详情={detail_name or '空'}")
        seen.add(name)
        rows.append(
            PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name,
                         duty=duty, detail_url=detail_result.final_url, evidence=duty,
                         confidence="high", parser=page_rule["parser"])
        )
    if not rows:
        raise RuntimeError("领导目录未解析到人物详情")
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
