from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1203",
    "domain": "jsgd.jiangsu.gov.cn",
    "page_type": "人物表格页",
    "structure_group": "jiangsu_broadcast_directory_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_jiangsu_broadcast_directory_profiles_v2",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "首人物链接与入口同址；隐藏访问计数iframe排除",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def compact_name(value: str) -> str:
    """移除姓名中的排版空白。"""
    return re.sub(r"\s+", "", clean_text(value))


def canonical_url(value: str) -> str:
    """移除查询、片段和末尾斜杠，供同址判断使用。"""
    parts = urlsplit(value)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def fetch_detail_html(detail_url: str, attempt_offset: int) -> str:
    """通过公共在线HTTP能力读取详情页，不落地缓存。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    result = fetch_by_raw_requests(detail_url, timeout=40, attempt_offset=attempt_offset)
    return result.html


def extract_profile(detail_html: str) -> tuple[str, str]:
    """按详情页br换行提取姓名和职务。"""
    profile = BeautifulSoup(detail_html, "html.parser").select_one(".ldxx span")
    if profile is None:
        return "", ""
    lines = [clean_text(line) for line in profile.get_text("\n", strip=True).splitlines()]
    lines = [line for line in lines if line]
    if len(lines) < 2:
        return "", ""
    return compact_name(lines[0]), clean_text(lines[1]).strip("，,；;。 ")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """继承领导目录顺序，在线读取对应详情页姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, link in enumerate(soup.select(".ldlb-txt a[href]"), start=1):
        listed_name = compact_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", listed_name) or listed_name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href", "")))
        same_as_entry = canonical_url(detail_url) == canonical_url(source_url)
        try:
            detail_html = html if same_as_entry else fetch_detail_html(detail_url, source_order)
        except Exception:
            continue
        name, duty = extract_profile(detail_html)
        if name != listed_name or not duty:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": "" if same_as_entry else detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；list=.ldlb-txt a[href]；"
                    "detail=.ldxx span br-separated-name-duty"
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
