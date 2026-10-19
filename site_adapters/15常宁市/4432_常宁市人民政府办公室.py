from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """清除排版空白，不改变页面文本语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def find_leader_index_url(html: str, final_url: str) -> str:
    """从当前部门入口动态发现本站“领导信息”栏目链接。"""
    soup = BeautifulSoup(html or "", "html.parser")
    current_path = urlparse(final_url).path.rstrip("/").lower()
    if current_path.endswith("/gzjg/ldxx") or current_path.endswith("/gzjg/ldxx/index.html"):
        return final_url

    candidates: list[str] = []
    for link in soup.select("a[href]"):
        label = clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
        href = clean_text(str(link.get("href") or ""))
        if label == "领导信息" and href:
            candidates.append(urljoin(final_url, href))
    unique = list(dict.fromkeys(candidates))
    if len(unique) != 1:
        raise RuntimeError(f"入口页领导信息栏目链接数量异常：{len(unique)}")
    return unique[0]


def extract_rows(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导栏目 DOM 顺序解析“完整现职：姓名”人物详情链接。"""
    soup = BeautifulSoup(html or "", "html.parser")
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for link in soup.select("a[href]"):
        href = clean_text(str(link.get("href") or ""))
        detail_url = urljoin(final_url, href)
        path = urlparse(detail_url).path.lower()
        if "/gzjg/ldxx/" not in path or not re.search(r"/\d{8}/i\d+\.html$", path):
            continue
        title = clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
        match = re.match(r"^(?P<duty>.+?)[：:]\s*(?P<name>[\u3400-\u9fff·]{2,10})$", title)
        if match is None or detail_url in seen_urls:
            continue
        duty = clean_text(match.group("duty")).rstrip("，,；;。 ")
        name = clean_text(match.group("name")).replace(" ", "")
        if not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "领导信息栏目内独立人物文章链接标题（完整现职：姓名）",
            }
        )
        seen_urls.add(detail_url)
    if not rows:
        raise RuntimeError("领导信息栏目未解析出“完整现职：姓名”人物详情链接")
    return rows


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从部门入口动态进入领导信息栏目并提取当前人物。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    leader_url = find_leader_index_url(html, final_url)
    if leader_url == final_url:
        return extract_rows(html, final_url, page_rule)
    result = fetch_html_with_strategy(leader_url, strategy="online", timeout=30, referer=final_url)
    return extract_rows(result.html, result.final_url, page_rule)


PAGE_RULE = {
    "rule_id": "4432",
    "domain": "www.hnchangning.gov.cn",
    "page_type": "部门入口转领导信息列表",
    "structure_group": "hnchangning_department_leader_list_v1",
    "reuse_scope": "same_site_department_template",
    "load_mode": "WAF 后的在线页面；入口动态发现领导栏目",
    "extract_mode": "list_to_detail",
    "parser": "page_hnchangning_department_leader_list_v1",
    "leader_region_selector": "领导信息栏目中的人物文章列表",
    "name_selector": "人物文章链接 title/text 最后一个冒号后的姓名",
    "duty_selector": "人物文章链接 title/text 最后一个冒号前的完整现职",
    "detail_link_selector": "领导信息栏目内 /gzjg/ldxx/YYYYMMDD/i数字.html",
    "detail_strategy": {"required": True, "mode": "dynamic_link"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "站点启用 WAF；必须排除入口导航与其他栏目，只接受领导信息路径下的独立人物文章",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
