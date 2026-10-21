from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0811",
    "page_type": "职务分组名单页",
    "structure_group": "gzpc_postmeta_grouped_leaders_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "gzpc_postmeta_grouped_leaders_v1",
    "leader_region_selector": ".column_con",
    "name_selector": "ul.infoList a[title]",
    "duty_selector": ".contit h3",
    "detail_link_selector": "ul.infoList a[href]",
    "content_scope": {
        "include_selectors": [".column_con"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "api_field",
        "detail_link_selector": "",
        "max_detail_links": 20,
    },
    "risk_flag": "人物列表由分组后的相邻脚本声明JSON接口，原始ul为空",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value).strip()


def _clean_name(value: str) -> str:
    name = re.sub(r"[（(].*?[）)]", "", _clean_text(value))
    return re.sub(r"\s+", "", name).strip()


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def _discover_api_url(section: object, final_url: str) -> str:
    """从当前分组后的实时脚本中发现JSON接口。"""
    script = section.find_next_sibling("script")
    if script is None:
        return ""
    match = re.search(r"var\s+url\s*=\s*['\"]([^'\"]+\.json)['\"]", script.get_text(" "))
    if match is None:
        return ""
    api_url = urljoin(final_url, match.group(1))
    if urlsplit(api_url).hostname != urlsplit(final_url).hostname:
        return ""
    return api_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按页面分组顺序发现JSON接口，并按接口人物数组顺序输出。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    entry_url = page_rule["url"]
    records: list[object] = []
    seen: set[str] = set()
    for section in soup.select(".column_con"):
        duty_node = section.select_one(".contit h3")
        if duty_node is None:
            continue
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        api_url = _discover_api_url(section, final_url)
        if not duty or not api_url:
            continue

        response = requests.get(
            api_url,
            headers={"User-Agent": "Mozilla/5.0", "Referer": final_url},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        category_duty = _clean_text(str(payload.get("category", {}).get("name", "")))
        if category_duty != duty:
            raise ValueError(f"页面职务与接口分组不一致：{duty!r} != {category_duty!r}")
        articles = payload.get("articles", [])
        if not isinstance(articles, list):
            raise ValueError("接口articles字段不是数组")

        for article in articles:
            if not isinstance(article, dict):
                continue
            raw_name = _clean_text(str(article.get("title", "")))
            name = _clean_name(raw_name)
            if name in seen or not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue
            detail_url = str(article.get("url", "")).strip()
            if (
                not detail_url
                or urlsplit(detail_url).hostname != urlsplit(final_url).hostname
                or _normalize_url(detail_url) == _normalize_url(entry_url)
            ):
                detail_url = ""
            seen.add(name)
            records.append(
                PersonRecord(
                    organization=page_rule["organization"],
                    url=entry_url,
                    name=name,
                    duty=duty,
                    detail_url=detail_url,
                    evidence=duty,
                    confidence="high",
                    parser=page_rule["parser"],
                    selector_summary=".column_con职务 + 相邻脚本动态发现postmeta JSON",
                )
            )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
