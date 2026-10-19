from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3247",
    "page_type": "人物目录详情页",
    "structure_group": "gansu_healthcare_leader_list_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "directory_detail",
    "collector": "browser_dom",
    "parser": "page_inline_gansu_healthcare_list_detail_v1",
    "leader_region_selector": ".default_pgContainer",
    "name_selector": ".default_pgContainer > li > a[href]",
    "duty_selector": "详情页 #zoom p 内完整现任句",
    "detail_link_selector": ".default_pgContainer > li > a[href]",
    "content_scope": {
        "start_anchor": "领导之窗",
        "end_anchor": "版权所有",
        "include_selectors": [".default_pgContainer"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "person_name_link",
        "detail_collector_type": "chrome",
        "detail_link_selector": ".default_pgContainer > li > a[href]",
        "detail_name_selector": "#zoom p b",
        "detail_duty_selector": "#zoom p 内完整现任句",
        "detail_content_selector": "#zoom",
        "max_detail_links": 20,
    },
    "risk_flag": "普通HTTP和Playwright受防护影响；当前仅使用Chrome CDP，并逐页校验列表姓名与详情姓名一致",
    "confidence": "high",
    "profile_reusable": "gansu_healthcare_chrome_list_detail_v1",
    "profile_judgement": "同站领导之窗列表与详情结构已在线逐页核验",
    "filter_policy": "strong_no_wordlist",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """压缩页面排版空白，不改变原文语义。"""
    return " ".join((value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导列表顺序逐页取得姓名、完整现任句和真实详情链接。"""
    del page_rule
    from crawler_core.fetcher import fetch_by_chrome_debug

    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(".default_pgContainer")
    if region is None:
        raise RuntimeError("Chrome页面未找到领导列表.default_pgContainer")

    anchors = region.select(":scope > li > a[href]")
    if not anchors:
        raise RuntimeError("领导列表未找到人物详情链接")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for anchor in anchors:
        name = re.sub(r"\s+", "", anchor.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name):
            raise RuntimeError(f"领导列表姓名格式异常：{name!r}")
        if name in seen_names:
            raise RuntimeError(f"领导列表出现重复姓名：{name}")

        detail_url = urljoin(final_url, str(anchor.get("href") or "").strip())
        parsed_detail = urlsplit(detail_url)
        if parsed_detail.netloc != urlsplit(final_url).netloc or not re.fullmatch(
            r"/ylbzj/c105254/\d{6}/\d+\.shtml",
            parsed_detail.path,
        ):
            raise RuntimeError(f"{name}详情链接不属于领导之窗人物页：{detail_url}")

        detail_result = fetch_by_chrome_debug(detail_url, timeout=45)
        detail_soup = BeautifulSoup(detail_result.html, "lxml")
        matched_paragraph = None
        evidence = ""
        for paragraph in detail_soup.select("#zoom p"):
            paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
            current_match = re.search(r"现任[^。]*。", paragraph_text)
            if current_match is not None:
                matched_paragraph = paragraph
                evidence = current_match.group(0).removeprefix("现任").removesuffix("。")
                break
        if matched_paragraph is None:
            raise RuntimeError(f"{name}详情页#zoom未找到完整现任句")

        detail_name_node = matched_paragraph.select_one("b, strong")
        detail_name = re.sub(
            r"\s+",
            "",
            detail_name_node.get_text(" ", strip=True) if detail_name_node else "",
        )
        if detail_name != name:
            raise RuntimeError(f"列表姓名与详情姓名不一致：{name} != {detail_name}")

        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_result.final_url,
                "confidence": "high",
                "parser": "page_inline_gansu_healthcare_list_detail_v1",
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
