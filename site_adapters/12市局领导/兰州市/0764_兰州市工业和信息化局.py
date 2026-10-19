from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0764',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML内嵌XML数据集',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_to_detail',
 'collector': 'browser_dom',
 'parser': 'page_inline_lanzhou_gxj_live_detail_after_share_v2',
 'leader_region_selector': 'a[href*="art_2696_"]',
 'name_selector': '链接文本日期前姓名',
 'duty_selector': '详情页分享X后首个职务片段',
 'detail_link_selector': 'a[href*="art_2696_"]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_link_selector': 'a[href*="art_2696_"]',
                     'max_detail_links': 50},
 'risk_flag': '目录人物位于script[type=text/xml]的record CDATA；职务只取详情页“分享：X”后的首个句段',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'a[href*="art_2696_"]',
                     'name_selector': '链接文本日期前姓名',
                     'duty_selector': '详情页分享X后首个职务片段',
                     'detail_link_selector': 'a[href*="art_2696_"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '浏览器渲染后的目录与详情页HTML已包含全部人物字段'}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录顺序在线抓取详情，并提取分享标记后的职务片段。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "html.parser")
    directory_soup = BeautifulSoup("", "html.parser")
    for data_script in soup.select('script[type="text/xml"]'):
        payload = str(data_script.string or data_script.get_text() or "")
        if "art_2696_" in payload:
            data_soup = BeautifulSoup(payload, "xml")
            record_html = "".join(str(record.string or "") for record in data_soup.find_all("record"))
            directory_soup = BeautifulSoup(record_html, "html.parser")
            break
    page_url = final_url or str(page_rule.get("url", ""))
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for link in directory_soup.select('a[href*="art_2696_"]'):
        text = re.sub(r"[\s\u3000\xa0]+", " ", link.get_text(" ", strip=True)).strip()
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,8})\s+\d{4}-\d{2}-\d{2}", text)
        detail_url = urljoin(page_url, str(link.get("href", "")))
        if match and detail_url not in seen_urls:
            seen_urls.add(detail_url)
            candidates.append((match.group("name"), detail_url))
    if not candidates:
        raise RuntimeError("领导班子目录未找到带姓名和日期的详情链接")

    rows: list[dict[str, str]] = []
    for name, detail_url in candidates:
        detail_html = fetch_by_raw_requests(detail_url, timeout=60).html
        detail_soup = BeautifulSoup(detail_html, "html.parser")
        detail_text = re.sub(r"[\s\u3000\xa0]+", " ", detail_soup.get_text(" ", strip=True)).strip()
        duty_match = re.search(r"分享\s*[:：]\s*X\s*(?P<duty>.+?)(?:[，,。])", detail_text)
        if duty_match is None:
            raise RuntimeError(f"{name} 详情页未找到分享标记后的职务片段")
        duty = duty_match.group("duty").strip()
        if not duty:
            raise RuntimeError(f"{name} 详情页职务为空")
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": page_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "a[href*=art_2696_]目录姓名和详情页；详情页分享X后首个职务片段",
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
