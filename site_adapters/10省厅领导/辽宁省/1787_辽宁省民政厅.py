from __future__ import annotations

import sys
import re
import subprocess
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from crawler_core.paths import find_powershell_executable


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1787',
 'domain': 'mzt.ln.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'liaoning_mzt_leader_detail_v1',
 'leader_region_selector': '.oflow-hd dd.ldname a',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def _fetch_detail_html(url: str) -> str:
    fetch_url = url.replace("https://mzt.ln.gov.cn/", "http://mzt.ln.gov.cn/", 1)
    request = Request(fetch_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=20) as response:
            body = response.read()
            encoding = response.headers.get_content_charset() or "utf-8"
        return body.decode(encoding, errors="replace")
    except Exception:
        command = (
            "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
            "(Invoke-WebRequest -Uri $args[0] -UseBasicParsing -TimeoutSec 20).Content"
        )
        result = subprocess.run(
            [str(find_powershell_executable()), "-NoProfile", "-Command", command, url],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        return result.stdout


def _extract_duty(detail_html: str, name: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    text = _clean_text(soup.get_text(" ", strip=True))
    match = re.search(r"现任(.+?)[。；;]", text)
    if match:
        return _clean_text(match.group(1)), match.group(0)

    title_node = soup.select_one(".xxgk_ldlxm")
    if title_node:
        title = _clean_text(title_node.get_text(" ", strip=True))
        duty = _clean_text(title.replace(name, ""))
        return duty, title
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析辽宁省民政厅部门领导列表，并从详情页抽取职务。"""
    soup = BeautifulSoup(html, "html.parser")
    records = []
    seen_names: set[str] = set()

    for link in soup.select(".oflow-hd dd.ldname a"):
        name = _clean_text(link.get_text(" ", strip=True))
        if not name or name in seen_names:
            continue
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue

        detail_url = urljoin(final_url, link.get("href", ""))
        try:
            duty, evidence = _extract_duty(_fetch_detail_html(detail_url), name)
        except Exception:
            duty, evidence = "", ""
        if not duty:
            continue

        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": "list=.oflow-hd dd.ldname a; detail=regex 现任 or .xxgk_ldlxm",
            }
        )

    return records


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
