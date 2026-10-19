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
    "rule_id": "2708",
    "domain": "tj.jiangsu.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "jiangsu_statistics_leader_navigation_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_jiangsu_statistics_leader_navigation_v2",
    "detail_strategy": {"required": False, "mode": "dynamic_from_list"},
    "risk_flag": "旧接口画像已过期；首人物链接与入口同址；隐藏访问计数iframe排除",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def canonical_url(value: str) -> str:
    """移除查询、片段和末尾斜杠，供同址判断使用。"""
    parts = urlsplit(value)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导目录DOM顺序拆分“职务 姓名”强结构文本。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".column-left .column-col > li > a[href]"):
        text = clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"(.+?)\s+([\u3400-\u9fff·]{2,5})", text)
        if match is None:
            continue
        duty, name = clean_text(match.group(1)), match.group(2)
        if not duty or name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href", "")))
        same_as_entry = canonical_url(detail_url) == canonical_url(source_url)
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
                    "strategy=custom_parse_page；"
                    "list=.column-left .column-col > li > a[href]；"
                    "fields=trailing-name-with-preceding-duty"
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
