from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3900",
    "page_type": "详情页侧栏候选逐页核验",
    "structure_group": "xuzhou_government_verified_details_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "requests",
    "parser": "page_inline_xuzhou_government_details_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".em-leader-nav",
    "name_selector": ".em-leader-name",
    "duty_selector": "详情.em-personal-profile内完整现任句",
    "detail_link_selector": ".em-leader-name[href]",
    "detail_timeout_seconds": 35,
    "risk_flag": "侧栏职务标签存在更新不同步；必须逐详情核验当前市政府任职并排除无现职证据候选",
    "confidence": "high",
    "filter_policy": "verified_current_sentence",
}


def clean_text(value: object) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅删除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def clean_current_sentence(value: str) -> str:
    """删除已定位现任句的句首固定标签和纯句末句号。"""
    evidence = re.sub(r"^现任\s*", "", clean_text(value), count=1)
    return evidence.removesuffix("。").strip()


def normalized_url(value: str) -> str:
    """统一协议、主机、末尾斜线并移除片段，用于同址判定。"""
    parts = urlparse(value)
    path = parts.path.rstrip("/") or "/"
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{path}?{parts.query}".rstrip("?")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按侧栏顺序逐页核验个人简介中的当前市政府任职。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "lxml")
    base_url = final_url or page_rule["url"]
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for link in soup.select("a.em-leader-name[href]"):
        name = clean_name(link.get_text(" ", strip=True))
        href = clean_text(link.get("href"))
        detail_url = urljoin(base_url, href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            continue
        if detail_url in seen_urls or urlparse(detail_url).scheme not in {"http", "https"}:
            continue
        seen_urls.add(detail_url)
        candidates.append((name, detail_url))

    rows: list[dict] = []
    seen_names: set[str] = set()
    for expected_name, detail_url in candidates:
        detail_result = fetch_html_with_strategy(
            detail_url,
            strategy="requests",
            timeout=int(page_rule["detail_timeout_seconds"]),
        )
        detail_soup = BeautifulSoup(detail_result.html, "lxml")
        profile = detail_soup.select_one(".em-personal-profile")
        profile_text = clean_text(profile.get_text(" ", strip=True) if profile else "")
        current_match = re.search(r"现任[^。]*。", profile_text)
        if expected_name not in profile_text or current_match is None:
            continue
        current_sentence = current_match.group(0)
        if "市政府" not in current_sentence and "人民政府" not in current_sentence:
            continue
        evidence = clean_current_sentence(current_sentence)
        if expected_name in seen_names or not evidence:
            continue
        resolved_detail_url = detail_result.final_url or detail_url
        if normalized_url(resolved_detail_url) in {
            normalized_url(page_rule["url"]),
            normalized_url(base_url),
        }:
            resolved_detail_url = ""
        seen_names.add(expected_name)
        rows.append(
            {
                "name": expected_name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": resolved_detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": "侧栏.em-leader-name候选；详情.em-personal-profile完整现任句",
            }
        )

    if not rows:
        raise RuntimeError("侧栏候选详情均缺少可核验的当前市政府任职")
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
