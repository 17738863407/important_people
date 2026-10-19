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
    "rule_id": "3017", "page_type": "人物目录详情页", "structure_group": "xian_json_list_detail_labels_v3",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page", "parser": "xian_json_list_detail_labels_v3",
    "leader_region_selector": "入口同路径/pages/1.json", "name_selector": ".m-txt-article .row内姓名标签相邻.txt",
    "duty_selector": ".m-txt-article .row内职务标签相邻.txt", "detail_link_selector": "JSON字段url",
    "detail_strategy": {"required": True, "mode": "json_list_to_detail", "max_detail_links": 20},
    "risk_flag": "入口HTML仅显示加载中，人物顺序和详情链接来自同路径分页JSON，姓名职务取详情页明确标签",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def field_value(card: object, keyword: str) -> str:
    for row in card.select(".row"):
        label, value = row.select_one(".tnm"), row.select_one(".txt")
        if label and value and re.sub(r"\s+", "", clean_text(label.get_text(" ", strip=True))).rstrip("：:") == keyword:
            return clean_text(value.get_text(" ", strip=True))
    return ""


def build_page_data_url(entry_url: str) -> str:
    parts = urlsplit(entry_url)
    path = re.sub(r"/\d+\.html$", "", parts.path.rstrip("/"))
    return urlunsplit((parts.scheme, parts.netloc, f"{path}/pages/1.json", "", ""))


def fetch_soup(session: requests.Session, url: str, referer: str) -> BeautifulSoup:
    response = session.get(
        url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0", "Referer": referer},
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    return BeautifulSoup(response.text, "html.parser")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    from crawler_core.models import PersonRecord

    session = requests.Session()
    list_response = session.get(
        build_page_data_url(final_url),
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0", "Referer": final_url},
    )
    list_response.raise_for_status()
    articles = list_response.json()
    if not isinstance(articles, list) or not articles:
        raise RuntimeError("领导分页JSON没有可验证人物记录")

    records: list[object] = []
    seen: set[str] = set()
    for article in articles:
        if not isinstance(article, dict):
            raise RuntimeError("领导分页JSON记录类型异常")
        listed_name = re.sub(r"\s+", "", clean_text(str(article.get("title") or article.get("resourceSummary") or "")))
        relative_url = clean_text(str(article.get("url") or ""))
        detail_url = urljoin(final_url, relative_url)
        if not relative_url or detail_url == final_url:
            raise RuntimeError(f"人物详情链接异常：{listed_name} {relative_url}")
        detail_soup = fetch_soup(session, detail_url, final_url)
        scope = detail_soup.select_one(".m-txt-article")
        if scope is None:
            raise RuntimeError(f"人物详情正文区域缺失：{detail_url}")
        name = re.sub(r"\s+", "", field_value(scope, "姓名"))
        evidence = field_value(scope, "职务")
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None or not evidence:
            raise RuntimeError(f"领导姓名或职务字段异常：{name} {evidence}")
        if listed_name != name:
            raise RuntimeError(f"列表与详情姓名不一致：{listed_name} / {name}")
        if name in seen:
            raise RuntimeError(f"领导姓名重复：{name}")
        seen.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("领导信息页没有可验证人物字段")
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
