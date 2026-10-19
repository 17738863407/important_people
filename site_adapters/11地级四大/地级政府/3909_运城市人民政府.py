from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3909",
    "page_type": "详情页侧栏候选逐页核验",
    "structure_group": "yuncheng_government_verified_details_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "list_to_detail",
    "collector": "requests",
    "parser": "page_inline_yuncheng_government_details_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".xxgk_box02 .LeftSide_con",
    "name_selector": "dl dt a[title]",
    "duty_selector": "详情.ld_intro个人简介内完整现任句",
    "detail_link_selector": "dl dt a[href][title]",
    "detail_timeout_seconds": 35,
    "risk_flag": "入口为市长详情页；必须限制市政府侧栏并逐详情核验现任句",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅删除姓名中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def clean_current_sentence(value: str) -> str:
    """清理已在人物简介内定位的完整现任句。"""
    evidence = re.sub(r"^现任\s*", "", clean_text(value), count=1)
    return evidence.removesuffix("。").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按市政府侧栏顺序抓取详情并核验当前任职。"""
    import requests

    soup = BeautifulSoup(html, "lxml")
    base_url = final_url or page_rule["url"]
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for link in soup.select(".xxgk_box02 .LeftSide_con dl dt a[href][title]"):
        name = clean_name(link.get("title") or link.get_text(" ", strip=True))
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
    session = requests.Session()
    session.trust_env = False
    headers = {"User-Agent": "Mozilla/5.0"}
    for expected_name, detail_url in candidates:
        response = session.get(
            detail_url,
            timeout=int(page_rule["detail_timeout_seconds"]),
            headers=headers,
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        detail_soup = BeautifulSoup(response.text, "lxml")
        profile_blocks = detail_soup.select(".ld_intro")
        profile_text = clean_text(" ".join(block.get_text(" ", strip=True) for block in profile_blocks))
        current_match = re.search(r"现任[^。]*。", profile_text)
        if expected_name not in profile_text or current_match is None:
            continue
        evidence = clean_current_sentence(current_match.group(0))
        if expected_name in seen_names or not evidence:
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
                "selector_summary": "市政府侧栏候选；详情.ld_intro个人简介完整现任句",
            }
        )

    if not rows:
        raise RuntimeError("市政府侧栏候选详情均缺少可核验的现任句")
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
