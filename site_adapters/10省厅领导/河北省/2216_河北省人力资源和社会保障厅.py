from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2216',
 'domain': 'rst.hebei.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_hebei_rst_api_detail_v1',
 'leader_region_selector': 'a[href*="article="]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
             'locator': {'css': {'leader_region_selector': 'a[href*="article="]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': True, 'reason': '在线详情接口返回 data.articleContent'},
             'migration': {'source': 'last_batch_online_template',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()
    return re.sub(r"\s*([、，])\s*", r"\1", normalized)


def extract_duty(content: str, name: str) -> str:
    text = clean_text(BeautifulSoup(content, "html.parser").get_text(" ", strip=True))
    if name not in text:
        return ""
    duty = clean_text(text.split(name, 1)[0])
    return duty.rstrip("，、")


def fetch_article_content(api_url: str, article_id: str) -> str:
    """通过项目统一采集器读取同站文章接口。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    request_url = f"{api_url}?{urlencode({'id': article_id})}"
    result = fetch_html_with_strategy(request_url, "raw_http")
    payload = json.loads(result.html)
    return str(((payload.get("data") or {}).get("articleContent") or ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    from crawler_core.fetcher import fetch_html_with_strategy

    page_url = str(page_rule.get("url", "")) or final_url
    parsed_page_url = urlsplit(page_url)
    api_url = f"{parsed_page_url.scheme}://{parsed_page_url.netloc}/rsmhapi/door/article"
    entry_html = html or ""
    directory_match = re.search(r"title:\s*['\"]厅领导['\"][^}]+articleId:\s*['\"]([^'\"]+)", entry_html)
    if not directory_match:
        entry_html = fetch_html_with_strategy(page_url, "raw_http").html
        directory_match = re.search(r"title:\s*['\"]厅领导['\"][^}]+articleId:\s*['\"]([^'\"]+)", entry_html)
    if not directory_match:
        return []
    directory_content = fetch_article_content(api_url, directory_match.group(1))
    soup = BeautifulSoup(directory_content, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = link.get("href") or ""
        if "article=" not in href:
            continue
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        article_ids = parse_qs(urlsplit(href).query).get("article") or []
        if not article_ids:
            continue
        detail_content = fetch_article_content(api_url, article_ids[0])
        duty_text = extract_duty(detail_content, name)
        if not duty_text:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty_text,
                "detail_url": href,
                "evidence": duty_text,
                "selector_summary": "列表article链接+接口JSON articleContent",
            }
        )

    return rows


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
