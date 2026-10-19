from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1474", "page_type": "人物目录详情页",
    "structure_group": "haikou_forestry_list_to_profile", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "requests", "extract_mode": "list_to_detail",
    "collector": "static_http", "parser": "builtin_parse_page", "leader_region_selector": ".lby-lm2",
    "name_selector": ".lby-lm2 a[title]", "duty_selector": "详情.content完整现任原句",
    "detail_link_selector": ".lby-lm2 a[title][href$='.shtml']",
    "detail_strategy": {"required": True, "mode": "list_to_detail", "detail_name_selector": ".docTitleCls",
                        "detail_content_selector": ".content", "max_detail_links": 50},
    "risk_flag": "排除汇总文章，逐一校验详情标题姓名并在当前人物内容区提取现任原句",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    for link in soup.select(".lby-lm2 a[title][href$='.shtml']"):
        name = compact_text(link.get("title") or link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name):
            continue
        candidates.append((name, urljoin(final_url, str(link.get("href") or ""))))
    if not candidates:
        raise ValueError("领导目录未发现有效姓名详情链接")
    rows: list[dict[str, str]] = []
    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        for name, detail_url in candidates:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            detail_soup = BeautifulSoup(response.text, "html.parser")
            title = detail_soup.select_one(".docTitleCls")
            content = detail_soup.select_one(".content")
            if title is None or compact_text(title.get_text(" ", strip=True)) != name:
                raise ValueError(f"详情标题姓名不一致：{name}")
            if content is None:
                raise ValueError(f"详情缺少人物内容容器：{name}")
            text = compact_text(content.get_text(" ", strip=True))
            match = re.search(r"(?P<evidence>现任(?P<duty>[^。]+)。)", text)
            if not match:
                raise ValueError(f"详情未发现现任职务原句：{name}")
            duty = match.group("duty").strip()
            rows.append({"name": name, "duty": duty, "evidence": duty,
                         "detail_url": response.url,
                         "selector_summary": ".lby-lm2姓名链接→详情标题校验→.content现任原句"})
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
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
