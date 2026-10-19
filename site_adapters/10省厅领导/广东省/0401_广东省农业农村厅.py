from __future__ import annotations

import sys
from pathlib import Path
import re
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0401',
 'domain': 'dara.gd.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'S_DARA_GD_GOV_CN_LEADER_DETAIL_V1',
 'leader_region_selector': 'body',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': "a[href*='ld']",
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'body',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': "a[href*='ld']",
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线浏览器 DOM 名单与在线详情页逐页解析'}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析广东省农业农村厅领导详情组：左侧名单链接，详情页正文为职务。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("ul.aside li a[href]"):
        name = _clean_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name):
            continue
        detail_url = urljoin(base_url, link.get("href") or "")
        if name in seen:
            continue
        seen.add(name)
        try:
            detail_html = html if detail_url == base_url else _fetch_html(detail_url)
            detail_name, duty, evidence = _parse_detail(detail_html, name)
        except Exception:
            detail_name, duty, evidence = name, "", ""
        if detail_url.rstrip("/") == base_url.rstrip("/"):
            detail_url = ""
        rows.append(
            {
                "name": detail_name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "confidence": "high",
                "parser": "S_DARA_GD_GOV_CN_LEADER_DETAIL_V1",
                "selector_summary": "ul.aside li a[href] + div.article p",
            }
        )
    return rows


def _fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=25) as response:
        data = response.read()
        content_type = response.headers.get("content-type", "")
    charset_match = re.search(r"charset=([\w-]+)", content_type, re.I)
    encodings = [charset_match.group(1)] if charset_match else []
    encodings.extend(["utf-8", "gb18030"])
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except Exception:
            continue
    return data.decode("utf-8", errors="ignore")


def _parse_detail(detail_html: str, fallback_name: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    meta_title = soup.select_one("meta[name='ArticleTitle']")
    name = _clean_name(meta_title.get("content") if meta_title else fallback_name)
    article = soup.select_one("div.article")
    if article is None:
        return name, "", ""
    article_text = _clean_text(article.get_text(" ", strip=True))
    current_match = re.search(r"现任[^。]*。", article_text)
    if current_match:
        evidence = current_match.group(0)
        return name, evidence.removeprefix("现任").rstrip("。"), evidence
    for paragraph in article.select("p"):
        text = _clean_text(paragraph.get_text(" ", strip=True)).strip("：:；;。")
        if len(text) <= 120 and re.search(r"党组|厅长|巡视员|纪检监察组|主任", text):
            return name, text, text
    return name, "", ""


def _clean_name(value: str | None) -> str:
    return re.sub(r"\s+", "", _clean_text(value or ""))


def _clean_text(value: str) -> str:
    text = re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip(" ：:\t\r\n")
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


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
