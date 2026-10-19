from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2487',
 'domain': 'slt.gd.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'article_leader_division_notice_gd_water_v1',
 'leader_region_selector': '.article-content p',
 'name_selector': '正文段首姓名',
 'duty_selector': '姓名后第一个逗号前正式职务',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"static_http","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.article-content p',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面直接提供领导班子成员分工正文'}}}


def _fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析广东省水利厅领导班子成员分工通知正文。"""
    source_url = str(page_rule["url"])
    soup = BeautifulSoup(html or "", "html.parser")
    article_nodes = soup.select(".article-content")
    if not article_nodes or not any("领导班子成员分工" in node.get_text(" ", strip=True) for node in article_nodes):
        soup = BeautifulSoup(_fetch_html(source_url), "html.parser")
        article_nodes = soup.select(".article-content")
    if not article_nodes:
        return []
    article = max(article_nodes, key=lambda node: len(node.get_text(" ", strip=True)))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in article.select("p"):
        raw_text = " ".join(paragraph.get_text(" ", strip=True).replace("\u3000", " ").split())
        match = re.match(r"^(?P<name>[\u4e00-\u9fff ]{2,7})\s+(?P<duty>[^，。]+)[，,]", raw_text)
        if not match:
            continue
        name = match.group("name").replace(" ", "")
        duty = match.group("duty").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or "厅" not in duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": str(page_rule["parser"]),
                "selector_summary": ".article-content p正文段首姓名和首个逗号前职务",
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
