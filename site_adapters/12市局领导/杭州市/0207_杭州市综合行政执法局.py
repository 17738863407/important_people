from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0207",
    "page_type": "人物目录详情页",
    "structure_group": "hangzhou_cgw_unit_api_profiles_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "requests",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "hangzhou_cgw_unit_api_profiles_v1",
    "leader_region_selector": "script[src*='unitbuild'][url][querydata]返回HTML",
    "name_selector": "接口HTML a[title][href]",
    "duty_selector": "详情表格职务行",
    "detail_link_selector": "接口HTML a[title][href]",
    "detail_strategy": {
        "required": True,
        "mode": "api_list_to_detail",
        "detail_name_selector": "详情表格领导姓名行",
        "detail_duty_selector": "详情表格职务行",
        "max_detail_links": 50,
    },
    "risk_flag": "入口目录由页面声明的公共构建接口加载，接口地址和参数从当前HTML动态读取",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value or "").strip()


def clean_value(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_label(value: str) -> str:
    return compact_text(value).rstrip("：:")


def valid_detail_url(href: str, final_url: str) -> str:
    """校验当前栏目下的站内人物详情路径。"""
    detail_url = urljoin(final_url, href)
    entry = urlparse(final_url)
    detail = urlparse(detail_url)
    if detail.netloc != entry.netloc:
        return ""
    if "/art/" not in detail.path or not detail.path.endswith(".html"):
        return ""
    return detail_url


def extract_directory(soup: BeautifulSoup, final_url: str, session: requests.Session) -> list[tuple[str, str]]:
    """读取入口页声明的构建接口并返回当前目录。"""
    script = soup.select_one("script[src*='unitbuild'][url][querydata]")
    if script is None:
        raise ValueError("入口页未发现目录构建接口声明")
    try:
        query_data = ast.literal_eval(script.get("querydata", ""))
    except (SyntaxError, ValueError) as exc:
        raise ValueError("目录构建接口参数无法解析") from exc
    if not isinstance(query_data, dict):
        raise ValueError("目录构建接口参数不是对象")
    api_url = urljoin(final_url, script.get("url", ""))
    if urlparse(api_url).netloc != urlparse(final_url).netloc:
        raise ValueError("目录构建接口不属于当前站点")
    response = session.get(api_url, params=query_data, timeout=30)
    response.raise_for_status()
    directory_html = response.json().get("data", {}).get("html", "")
    directory_soup = BeautifulSoup(directory_html, "html.parser")
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for link in directory_soup.select("a[title][href]"):
        name = compact_text(link.get("title", ""))
        detail_url = valid_detail_url(link.get("href", ""), final_url)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name) or not detail_url or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        candidates.append((name, detail_url))
    if not candidates:
        raise ValueError("目录构建接口未返回有效人物链接")
    return candidates


def extract_detail_fields(detail_soup: BeautifulSoup) -> dict[str, str]:
    """按详情表格的字段标签读取值。"""
    fields: dict[str, str] = {}
    for row in detail_soup.select("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) < 2:
            continue
        label = normalize_label(cells[0].get_text(" ", strip=True))
        value = clean_value(cells[1].get_text(" ", strip=True))
        if label:
            fields[label] = value
    return fields


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """通过入口声明接口动态发现人物，再逐详情解析姓名和职务强字段。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        for link_name, detail_url in extract_directory(soup, final_url, session):
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            fields = extract_detail_fields(BeautifulSoup(response.text, "html.parser"))
            detail_name = compact_text(fields.get("领导姓名", fields.get("姓名", "")))
            duty = fields.get("职务", fields.get("现任职务", ""))
            if detail_name != link_name or not duty:
                raise ValueError(f"详情姓名或职务字段校验失败：{link_name}")
            records.append(
                {
                    "name": detail_name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": response.url,
                    "selector_summary": "入口脚本构建接口→当前目录→详情表格领导姓名/职务行",
                }
            )
    return records


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
