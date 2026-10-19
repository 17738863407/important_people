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


PAGE_RULE = {
    "rule_id": "0732",
    "domain": "glj.jiangsu.gov.cn",
    "page_type": "人物目录详情页",
    "structure_group": "jiangsu_government_office_directory_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_jiangsu_government_office_directory_profiles_v2",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "普通请求可能触发云防御；目录必须限定到xxgk_list领导分组；隐藏访问计数iframe排除",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def fetch_detail_profile(detail_url: str, attempt_offset: int) -> tuple[str, str]:
    """在线读取详情页强结构姓名与职务，不落地缓存。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    result = fetch_by_raw_requests(detail_url, timeout=40, attempt_offset=attempt_offset)
    soup = BeautifulSoup(result.html, "html.parser")
    profile = soup.select_one(".sec03 .ldjj-top-r")
    paragraphs = profile.find_all("p", recursive=False) if profile else []
    if len(paragraphs) < 2:
        return "", ""
    name = re.sub(r"\s+", "", clean_text(paragraphs[0].get_text(" ", strip=True)))
    duty = clean_text(paragraphs[1].get_text(" ", strip=True)).strip("，,；;。 ")
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """继承领导目录顺序，逐页在线读取对应人物职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, link in enumerate(
        soup.select("ul.xxgk_list > li.cf > a[href]"),
        start=1,
    ):
        name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href", "")))
        try:
            detail_name, duty = fetch_detail_profile(detail_url, source_order)
        except Exception:
            continue
        if detail_name != name or not duty:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；list=ul.xxgk_list>li.cf>a[href]；"
                    "detail=.sec03 .ldjj-top-r direct-name-duty-paragraphs"
                ),
            }
        )

    return records


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
