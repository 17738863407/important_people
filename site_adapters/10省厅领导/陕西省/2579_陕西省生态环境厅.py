from __future__ import annotations

import re
import sys
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2579',
 'domain': 'sthjt.shaanxi.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_shaanxi_ecology_leader_links_v1',
 'leader_region_selector': '.ldy-content领导简介链接',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': 'html > body > div.content.container:nth-of-type(1) > '
                                               'div.main-box.content-center > div.am-g.ldy-content',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '领导简介链接文本直接包含姓名和职务'}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    content_url = final_url or str(page_rule.get("url", ""))
    if soup.select_one(".ldy-content") is None:
        refresh = soup.select_one('meta[http-equiv][content]')
        refresh_match = re.search(r"url\s*=\s*(.+)$", refresh.get("content", ""), re.IGNORECASE) if refresh else None
        if refresh_match:
            redirect_url = urljoin(content_url, refresh_match.group(1).strip(" '\""))
            request = Request(redirect_url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=20) as response:
                html = response.read().decode("utf-8", errors="ignore")
                content_url = response.geturl()
            soup = BeautifulSoup(html, "html.parser")
    box = soup.select_one(".ldy-content") or soup
    rows: list[dict] = []
    seen: set[str] = set()
    duty_start = r"(?:党组|一级|二级|纪检|生态环境保护督察)"
    pattern = re.compile(rf"^(?P<name>.+?)\s+(?P<duty>{duty_start}.+)$")
    for link in box.find_all("a", href=True):
        text = _clean_text(link.get_text(" ", strip=True))
        if text in {"领导简介", "更多+"}:
            continue
        match = pattern.match(text)
        if not match:
            continue
        name = _clean_name(match.group("name"))
        duty = _clean_text(match.group("duty"))
        if not name or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": urljoin(content_url, link.get("href") or ""),
                "evidence": duty,
                "parser": "custom_shaanxi_ecology_leader_links_v1",
                "selector_summary": ".ldy-content领导链接文本",
                "order": str(len(rows) + 1),
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
