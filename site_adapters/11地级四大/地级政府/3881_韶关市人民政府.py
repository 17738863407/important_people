from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3881",
    "page_type": "人物目录详情页",
    "structure_group": "shaoguan_government_playwright_details_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "browser_dom",
    "parser": "page_inline_shaoguan_government_details_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "ul.sideMenu",
    "name_selector": "li a[href]",
    "duty_selector": ".ldzc-grjl内完整现任句",
    "detail_link_selector": "li a[href]",
    "detail_timeout_seconds": 45,
    "risk_flag": "普通HTTP被云防护拦截；入口跳转首位详情，需按侧栏顺序逐页渲染并限定简历块",
    "confidence": "high",
    "filter_policy": "weak_allow_wordlist",
}


def clean_text(value: object) -> str:
    """压缩页面排版空白，不改变现任句中的职务语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅删除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def clean_current_sentence(value: str) -> str:
    """删除已定位现任句的句首固定标签和纯句末句号。"""
    evidence = re.sub(r"^现任\s*", "", clean_text(value), count=1)
    evidence = re.sub(r"\s+", "", evidence)
    return evidence.removesuffix("。").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按侧栏原始顺序逐一渲染详情，并在简历块内提取完整现任句。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到领导之窗侧栏")

    base_url = final_url or page_rule["url"]
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for link in region.select(page_rule["detail_link_selector"]):
        name = clean_name(link.get_text(" ", strip=True))
        href = clean_text(link.get("href"))
        detail_url = urljoin(base_url, href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            continue
        if not detail_url or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        candidates.append((name, detail_url))

    rows: list[dict] = []
    seen_names: set[str] = set()
    for expected_name, detail_url in candidates:
        detail_result = fetch_html_with_strategy(
            detail_url,
            strategy="playwright",
            timeout=int(page_rule["detail_timeout_seconds"]),
        )
        detail_soup = BeautifulSoup(detail_result.html, "lxml")
        resume = detail_soup.select_one(".ldzc-grjl")
        resume_text = clean_text(resume.get_text(" ", strip=True) if resume else "")
        current_match = re.search(r"现任[^。]*。", resume_text)
        if expected_name not in resume_text or current_match is None:
            raise RuntimeError(
                f"详情简历缺少对应姓名或完整现任句：{expected_name} / {detail_result.final_url}"
            )
        evidence = clean_current_sentence(current_match.group(0))
        if expected_name in seen_names:
            continue

        seen_names.add(expected_name)
        rows.append(
            {
                "name": expected_name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_result.final_url or detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": "ul.sideMenu人物链接；详情.ldzc-grjl内完整现任句",
            }
        )

    if not rows:
        raise RuntimeError("领导详情页未提取到有效人物")
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
