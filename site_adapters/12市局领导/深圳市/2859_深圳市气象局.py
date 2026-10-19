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
    "rule_id": "2859",
    "page_type": "人物目录详情页",
    "structure_group": "shenzhen_openinfo_leader_documents",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "list_to_detail",
    "collector": "browser_dom",
    "leader_region_selector": "a.document-number[href]",
    "name_selector": "a.document-number[href]",
    "detail_link_selector": "a.document-number[href]",
    "risk_flag": "目录需浏览器渲染，详情正文还含工作分工且必须排除",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(text: str) -> str:
    """清理姓名和职务中的排版空白。"""
    return re.sub(r"\s+", "", text or "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按渲染目录顺序抓取详情正文首个“职务：姓名”字段。"""
    from crawler_core.fetcher import fetch_by_requests

    soup = BeautifulSoup(html, "html.parser")
    links = soup.select("a.document-number[href]")
    rows: list[dict[str, str]] = []
    errors: list[str] = []
    seen_urls: set[str] = set()
    for source_order, link in enumerate(links, start=1):
        menu_name = clean_text(link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(link.get("href") or "").strip())
        if not menu_name or not detail_url or detail_url in seen_urls:
            errors.append(f"目录第{source_order}项无有效姓名或详情链接")
            continue
        seen_urls.add(detail_url)
        try:
            result = fetch_by_requests(detail_url)
        except Exception as error:
            errors.append(f"{menu_name}详情抓取失败：{error}")
            continue
        detail_soup = BeautifulSoup(result.html, "html.parser")
        field = detail_soup.select_one("div.article-content strong")
        compact = clean_text(field.get_text(" ", strip=True) if field else "")
        match = re.fullmatch(r"(?P<duty>[^：:]+)[：:](?P<name>[一-鿿·]{2,4})", compact)
        if match is None or match.group("name") != menu_name:
            errors.append(f"目录第{source_order}项与详情姓名职务字段不一致")
            continue
        duty = match.group("duty")
        rows.append(
            {
                "order": str(source_order),
                "name": menu_name,
                "duty": duty,
                "evidence": duty,
                "detail_url": result.final_url,
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": "inline_shenzhen_weather_leader_documents_v1",
            }
        )
    if errors or len(rows) != len(links):
        raise RuntimeError("；".join(errors) or "领导目录详情未完整解析")
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
