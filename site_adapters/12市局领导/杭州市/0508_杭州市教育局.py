from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0508",
    "page_type": "人物目录详情页",
    "structure_group": "hangzhou_education_unit_api_profiles_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "requests",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "hangzhou_education_unit_api_profiles_v1",
    "leader_region_selector": "构建接口返回的本机关负责人.page-content",
    "name_selector": ".page-content a[title][href]",
    "duty_selector": "详情.leader_box2职务行",
    "detail_link_selector": ".page-content a[title][href]",
    "detail_strategy": {
        "required": True,
        "mode": "api_list_to_detail",
        "detail_name_selector": ".pc .art_tit, h2.art_tit",
        "detail_duty_selector": ".leader_box2职务行",
        "max_detail_links": 30,
    },
    "risk_flag": "入口含多个构建接口，仅接受标题为本机关负责人的返回片段",
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
    detail_url = urljoin(final_url, href)
    entry = urlparse(final_url)
    detail = urlparse(detail_url)
    if detail.netloc != entry.netloc:
        return ""
    if "/art/" not in detail.path or not detail.path.endswith(".html"):
        return ""
    return detail_url


def request_unit_html(script: object, final_url: str, session: requests.Session) -> str:
    """请求单个由入口声明的构建接口片段。"""
    try:
        query_data = ast.literal_eval(script.get("querydata", ""))
    except (SyntaxError, ValueError) as exc:
        raise ValueError("构建接口参数无法解析") from exc
    if not isinstance(query_data, dict):
        raise ValueError("构建接口参数不是对象")
    api_url = urljoin(final_url, script.get("url", ""))
    if urlparse(api_url).netloc != urlparse(final_url).netloc:
        raise ValueError("构建接口不属于当前站点")
    response = session.get(api_url, params=query_data, timeout=30)
    response.raise_for_status()
    return response.json().get("data", {}).get("html", "")


def extract_directory(soup: BeautifulSoup, final_url: str, session: requests.Session) -> list[tuple[str, str]]:
    """从多个构建接口中定位本机关负责人目录。"""
    directory_soup: BeautifulSoup | None = None
    for script in soup.select("script[src*='unitbuild'][url][querydata]"):
        unit_html = request_unit_html(script, final_url, session)
        unit_soup = BeautifulSoup(unit_html, "html.parser")
        heading = unit_soup.select_one(".zfxxgk_zdgktit")
        if heading and compact_text(heading.get_text(" ", strip=True)) == "本机关负责人":
            directory_soup = unit_soup
            break
    if directory_soup is None:
        raise ValueError("入口声明的构建接口未返回本机关负责人目录")
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for link in directory_soup.select(".page-content a[title][href]"):
        name = compact_text(link.get("title", ""))
        detail_url = valid_detail_url(link.get("href", ""), final_url)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name) or not detail_url or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        candidates.append((name, detail_url))
    if not candidates:
        raise ValueError("本机关负责人目录未返回有效人物链接")
    return candidates


def extract_duty(detail_soup: BeautifulSoup) -> str:
    """从领导详情表格的职务行读取原始值。"""
    for row in detail_soup.select(".leader_box2 tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) >= 2 and normalize_label(cells[0].get_text(" ", strip=True)) == "职务":
            return clean_value(cells[1].get_text(" ", strip=True))
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """动态发现本机关负责人目录，再逐详情解析标题姓名与职务行。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        for link_name, detail_url in extract_directory(soup, final_url, session):
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            detail_soup = BeautifulSoup(response.text, "html.parser")
            title = detail_soup.select_one(".pc .art_tit, h2.art_tit")
            detail_name = compact_text(title.get_text(" ", strip=True)) if title else ""
            duty = extract_duty(detail_soup).removesuffix("。")
            if detail_name != link_name or not duty:
                raise ValueError(f"详情标题或职务行校验失败：{link_name}")
            records.append(
                {
                    "name": detail_name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": response.url,
                    "selector_summary": "入口构建接口→本机关负责人目录→详情标题和.leader_box2职务行",
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
