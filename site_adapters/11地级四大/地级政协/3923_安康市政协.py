from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3923",
    "page_type": "分页人物卡片逐详情简介",
    "structure_group": "ankang_cppcc_paginated_details_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML分页",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "list_to_detail",
    "collector": "raw_http",
    "parser": "page_inline_ankang_cppcc_details_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "ul.zhuxiBox",
    "name_selector": "li a span",
    "duty_selector": "详情.ldjieshao内完整现任句",
    "detail_link_selector": "li a[href]",
    "page_limit": 5,
    "timeout_seconds": 35,
    "risk_flag": "列表共两页；必须动态跟随下一页并恢复分页及卡片顺序",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """删除姓名中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def clean_current_sentence(value: str) -> str:
    """清理已限定在人物简介内的现任句。"""
    evidence = re.sub(r"^现任\s*", "", clean_text(value), count=1)
    return evidence.removesuffix("。").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按分页与卡片顺序收集候选，再逐详情核验当前职务。"""
    import requests

    base_url = final_url or page_rule["url"]
    session = requests.Session()
    session.trust_env = False
    headers = {"User-Agent": "Mozilla/5.0"}
    candidates: list[tuple[str, str]] = []
    seen_pages: set[str] = set()
    seen_details: set[str] = set()
    page_url = base_url
    page_html = html
    for _ in range(int(page_rule["page_limit"])):
        if page_url in seen_pages:
            break
        seen_pages.add(page_url)
        soup = BeautifulSoup(page_html, "lxml")
        for link in soup.select("ul.zhuxiBox li a[href]"):
            name_node = link.select_one("span")
            name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
            detail_url = urljoin(page_url, clean_text(link.get("href")))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
                continue
            if detail_url in seen_details or urlparse(detail_url).scheme not in {"http", "https"}:
                continue
            seen_details.add(detail_url)
            candidates.append((name, detail_url))
        next_link = next(
            (
                link
                for link in soup.select(".pageBox a[href]")
                if clean_text(link.get_text(" ", strip=True)) == "下一页"
                and not clean_text(link.get("href")).lower().startswith("javascript:")
            ),
            None,
        )
        if next_link is None:
            break
        page_url = urljoin(page_url, clean_text(next_link.get("href")))
        response = session.get(
            page_url,
            timeout=int(page_rule["timeout_seconds"]),
            headers=headers,
            verify=False,
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        page_html = response.text

    rows: list[dict] = []
    seen_names: set[str] = set()
    for expected_name, detail_url in candidates:
        response = session.get(
            detail_url,
            timeout=int(page_rule["timeout_seconds"]),
            headers=headers,
            verify=False,
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        detail_soup = BeautifulSoup(response.text, "lxml")
        profile = detail_soup.select_one(".ldright .ldjieshao")
        profile_text = clean_text(profile.get_text(" ", strip=True) if profile else "")
        current_match = re.search(r"现任[^。]*(?:。|$)", profile_text)
        if expected_name not in profile_text or current_match is None:
            continue
        evidence = clean_current_sentence(current_match.group(0))
        if not evidence or expected_name in seen_names:
            continue
        seen_names.add(expected_name)
        rows.append(
            {
                "name": expected_name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": response.url or detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": "分页ul.zhuxiBox候选；详情.ldjieshao现任句",
            }
        )

    if not rows:
        raise RuntimeError("分页领导候选详情均未取得可核验的现任句")
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
