from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def find_leader_url(html: str, final_url: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    if re.search(r"/gzjg/ldxx(?:/index\.html)?/?$", urlparse(final_url).path, re.I):
        return final_url
    urls = list(dict.fromkeys(urljoin(final_url, str(a.get("href"))) for a in soup.select("a[href]") if clean_text(str(a.get("title") or a.get_text(" ", strip=True))) == "领导信息"))
    if len(urls) != 1:
        raise RuntimeError(f"入口页领导信息栏目链接数量异常：{len(urls)}")
    return urls[0]


def extract_rows(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in BeautifulSoup(html or "", "html.parser").select("a[href]"):
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if detail_url in seen or not re.search(r"/gzjg/ldxx/\d{8}/i\d+\.html$", urlparse(detail_url).path, re.I):
            continue
        title = clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
        match = re.match(r"^(?P<duty>.+?)[：:]\s*(?P<name>[\u3400-\u9fff·]{2,10})$", title)
        if match is None:
            match = re.match(r"^(?P<duty>.+\D)\s+(?P<name>[\u3400-\u9fff·]{2,10})$", title)
        if match is None:
            continue
        duty = clean_text(match.group("duty")).rstrip("，,；;。 ")
        name = clean_text(match.group("name")).replace(" ", "")
        if duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url, "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": "领导信息栏目独立人物文章链接标题"})
            seen.add(detail_url)
    if not rows:
        raise RuntimeError("领导信息栏目未解析出人物详情链接")
    return rows


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_html_with_strategy
    leader_url = find_leader_url(html, final_url)
    if leader_url == final_url:
        return extract_rows(html, final_url, page_rule)
    result = fetch_html_with_strategy(leader_url, strategy="online", timeout=30, referer=final_url)
    return extract_rows(result.html, result.final_url, page_rule)


PAGE_RULE = {"rule_id": "4437", "domain": "www.hnchangning.gov.cn", "page_type": "部门入口转领导信息列表", "structure_group": "hnchangning_department_leader_list_v1", "reuse_scope": "same_site_department_template", "load_mode": "WAF 后在线页面；动态发现领导栏目", "extract_mode": "list_to_detail", "parser": "page_hnchangning_department_leader_list_v1", "leader_region_selector": "领导信息栏目人物文章列表", "name_selector": "人物文章链接标题末尾姓名", "duty_selector": "人物文章链接标题中的完整现职", "detail_link_selector": "/gzjg/ldxx/YYYYMMDD/i数字.html", "detail_strategy": {"required": True, "mode": "dynamic_link"}, "locator_strategy": "custom_parse_page", "risk_flag": "站点启用 WAF；仅接受领导信息路径下的独立人物文章", "confidence": "high", "filter_policy": "strong_no_wordlist"}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()




