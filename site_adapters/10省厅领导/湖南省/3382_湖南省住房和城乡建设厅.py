from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3382',
 'domain': 'zjt.hunan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': 'iframe嵌入',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'hunan_housing_construction_detail_profiles_v1',
 'leader_region_selector': 'html > body > div.bg:nth-of-type(1)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'list_to_detail'},
 'risk_flag': '页面包含iframe；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': 'html > body > div.bg:nth-of-type(1)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '领导简介列表和详情页均在线解析'}}}


def _fetch_detail(detail_url: str) -> str:
    """在线读取详情；该站 HTTPS 偶发握手失败时兼容 HTTP。"""
    candidates = [detail_url]
    if detail_url.startswith("https://"):
        candidates.append("http://" + detail_url.removeprefix("https://"))
    for candidate in candidates:
        try:
            request = Request(candidate, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=20) as response:
                return response.read().decode("utf-8", errors="ignore")
        except Exception:
            continue
    return ""


def _current_sentence(detail_html: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
    match = re.search(r"现任[^。]*。", text)
    if not match:
        return ""
    evidence = re.sub(r"^现任\s*", "", match.group(0)).rstrip("。").strip()
    return re.sub(r"[（(]\s*兼\s*[）)]", "", evidence).strip(" ，,；;")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按原 div.bg 领导简介列表顺序在线读取人物详情现任句。"""
    organization = str(page_rule["organization"])
    source_url = str(page_rule["url"])
    parser = str(page_rule["parser"])
    selector_summary = "原 div.bg 领导简介链接 + 详情页现任完整句"
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("html > body > div.bg:nth-of-type(1)")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    if region is None:
        return rows
    for link in region.select("a[href]"):
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, link.get("href") or "")
        if urlparse(detail_url).netloc.lower() != urlparse(final_url).netloc.lower():
            continue
        if not re.search(r"/ldjj/\d{6}/t\d+_\d+\.html$", urlparse(detail_url).path):
            continue
        evidence = _current_sentence(_fetch_detail(detail_url))
        if not evidence:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": source_url,
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": parser,
                "selector_summary": selector_summary,
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
