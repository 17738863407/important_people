from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2746", "page_type": "人物列表完整页", "structure_group": "wuhan_statistics_list_detail_duty_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page", "parser": "wuhan_statistics_list_detail_duty_v2",
    "leader_region_selector": ".content ul.news_list", "name_selector": "li > a[href]",
    "duty_selector": "详情页.article .resume-area职责p开头职务字段", "detail_link_selector": ".content ul.news_list > li > a[href]",
    "detail_strategy": {"required": True, "mode": "list_link_and_detail_field", "detail_link_selector": ".content ul.news_list > li > a[href]", "max_detail_links": 20},
    "risk_flag": "列表仅含姓名，职务位于详情页职责p开头并以排版空白接职责正文；必须在线逐页回指且排除职责正文；HTTP头声明ISO-8859-1但正文为UTF-8",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_entry_soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html or "", "html.parser")
    fields = soup.select(".content ul.news_list > li > a[href]")
    names = [re.sub(r"\s+", "", clean_text(x.get_text(" ", strip=True))) for x in fields]
    if fields and not any(re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) for name in names):
        try:
            soup = BeautifulSoup((html or "").encode("latin-1").decode("utf-8"), "html.parser")
        except (UnicodeEncodeError, UnicodeDecodeError) as exc:
            raise RuntimeError(f"入口页UTF-8乱码严格回转失败：{exc}") from exc
    return soup


def fetch_detail_duty(session: requests.Session, detail_url: str, expected_name: str) -> str:
    response = session.get(detail_url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.content.decode("utf-8"), "html.parser")
    area = soup.select_one(".article .resume-area")
    name_node = area.select_one("h2") if area else None
    duty_node = area.select_one("p") if area else None
    detail_name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
    raw_field = duty_node.get_text("", strip=True) if duty_node else ""
    match = re.match(r"^(?P<duty>.+?)(?:\s{2,}|\s+(?=主持|负责|分管|完成|协助))", raw_field)
    if detail_name != expected_name or match is None:
        raise RuntimeError(f"详情页姓名或职责职务边界异常：{expected_name} {detail_name} {clean_text(raw_field)}")
    evidence = clean_text(match.group("duty"))
    if not evidence:
        raise RuntimeError(f"详情页原始职务为空：{expected_name}")
    return evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    from crawler_core.models import PersonRecord
    soup = parse_entry_soup(html); regions = soup.select(".content ul.news_list")
    if len(regions) != 1:
        raise RuntimeError(f"领导列表区域数量异常：{len(regions)}")
    records: list[object] = []; seen_names: set[str] = set(); seen_links: set[str] = set()
    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        for item in regions[0].select(":scope > li"):
            link = item.select_one(":scope > a[href]")
            name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True) if link else ""))
            detail_url = urljoin(final_url, link.get("href", "").strip() if link else ""); parts = urlsplit(detail_url)
            if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None:
                raise RuntimeError(f"领导列表姓名异常：{name}")
            if parts.scheme not in {"http", "https"} or not parts.netloc or detail_url == final_url:
                raise RuntimeError(f"领导详情链接异常：{name} {detail_url}")
            if name in seen_names or detail_url in seen_links:
                raise RuntimeError(f"领导姓名或详情链接重复：{name} {detail_url}")
            evidence = fetch_detail_duty(session, detail_url, name)
            seen_names.add(name); seen_links.add(detail_url)
            records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("领导列表没有可验证人物详情")
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
