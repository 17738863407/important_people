from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3915",
    "page_type": "领导列表逐详情字段",
    "structure_group": "zhaoqing_government_list_to_details_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "list_to_detail",
    "collector": "raw_http",
    "parser": "page_inline_zhaoqing_government_details_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".comlist",
    "name_selector": ".comlist a[title]及详情姓名字段",
    "duty_selector": "详情span_blue职务字段",
    "detail_link_selector": ".comlist a[href][title]",
    "detail_timeout_seconds": 35,
    "risk_flag": "列表仅含姓名和日期；职务必须逐详情字段核验",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """删除姓名中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def extract_labeled_value(soup: BeautifulSoup, label: str) -> str:
    """从明确标签所在段落读取标签后的完整字段值。"""
    for marker in soup.select("span.span_blue"):
        if clean_text(marker.get_text(" ", strip=True)).rstrip("：:") != label:
            continue
        parent = marker.parent
        full_text = clean_text(parent.get_text(" ", strip=True)) if parent else ""
        return re.sub(rf"^{re.escape(label)}[：:]\s*", "", full_text, count=1).strip()
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按列表顺序逐详情读取姓名与职务强字段。"""
    import requests

    soup = BeautifulSoup(html, "lxml")
    base_url = final_url or page_rule["url"]
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for link in soup.select(".comlist li a[href][title]"):
        expected_name = clean_name(link.get("title") or link.get_text(" ", strip=True))
        href = clean_text(link.get("href"))
        detail_url = urljoin(base_url, href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", expected_name):
            continue
        if detail_url in seen_urls or urlparse(detail_url).scheme not in {"http", "https"}:
            continue
        seen_urls.add(detail_url)
        candidates.append((expected_name, detail_url))

    session = requests.Session()
    session.trust_env = False
    rows: list[dict] = []
    seen_names: set[str] = set()
    for expected_name, detail_url in candidates:
        response = session.get(
            detail_url,
            timeout=int(page_rule["detail_timeout_seconds"]),
            headers={"User-Agent": "Mozilla/5.0"},
            verify=False,
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        detail_soup = BeautifulSoup(response.text, "lxml")
        name = clean_name(extract_labeled_value(detail_soup, "姓名"))
        evidence = clean_text(extract_labeled_value(detail_soup, "职务"))
        if name != expected_name or not evidence or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": response.url or detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": ".comlist候选；详情span.span_blue姓名/职务字段",
            }
        )

    if not rows:
        raise RuntimeError("领导列表详情均未取得匹配的姓名与职务字段")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
