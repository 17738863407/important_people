from __future__ import annotations

import sys
import re
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

PAGE_RULE = {'rule_id': '3240',
 'domain': 'yjt.hunan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'page_detail_online_hunan_emergency_leader_v1',
 'leader_region_selector': '.main a[href*="/jgld/"] span',
 'name_selector': 'span',
 'duty_selector': '',
 'detail_link_selector': '.main a[href*="/jgld/"]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '页面包含iframe；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.main a[href*="/jgld/"] span',
                     'name_selector': 'span',
                     'duty_selector': '',
                     'detail_link_selector': '.main a[href*="/jgld/"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def detail_duty(detail_html: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    for item in soup.select("div.zz"):
        label = item.select_one("i")
        value = item.select_one("em")
        if not label or not value:
            continue
        if "职位" in label.get_text("", strip=True):
            return re.sub(r"\s+", " ", value.get_text(" ", strip=True)).strip()
    return ""


def fetch_detail(detail_url: str) -> str:
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


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按原领导列表顺序发现人物链接，并在线读取详情页职位。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = rule["organization"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".hy-list-text a[href]"):
        name = re.sub(r"\s+", "", link.get_text("", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(base_url or rule["url"], link.get("href", ""))
        if urlparse(detail_url).netloc.lower() != urlparse(base_url or rule["url"]).netloc.lower():
            continue
        if not re.search(r"/jgld/\d{6}/t\d+_\d+\.html$", urlparse(detail_url).path):
            continue
        duty = detail_duty(fetch_detail(detail_url))
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": ".hy-list-text a + 在线详情 div.zz 职位",
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
