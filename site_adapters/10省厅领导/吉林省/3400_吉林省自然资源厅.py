from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3400',
 'domain': 'zrzy.jl.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_detail_online_jilin_natural_resources_leader_v1',
 'leader_region_selector': '领导之窗 a[href*="/ldzc/"]',
 'name_selector': '领导链接文本',
 'duty_selector': '详情开头姓名前职务',
 'detail_link_selector': 'a[href*="/ldzc/"]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '新闻人物或正文干扰；页面包含iframe；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '领导之窗 a[href*="/ldzc/"]',
                     'name_selector': '领导链接文本',
                     'duty_selector': '详情开头姓名前职务',
                     'detail_link_selector': 'a[href*="/ldzc/"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def _fetch_detail(detail_url: str) -> str:
    request = Request(detail_url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="ignore")


def _parse_detail_duty(detail_html: str, name: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(detail_html, "html.parser")
    content = soup.select_one(".content") or soup
    text = re.sub(r"[\s\u00a0\u3000]+", " ", content.get_text(" ", strip=True))
    spaced_name = r"\s*".join(map(re.escape, name))
    matches = re.findall(rf"([\u4e00-\u9fa5、，\s（）()]+?){spaced_name}\s*：", text)
    if not matches:
        return ""
    duty = re.sub(r"\s+", "", matches[0]).rstrip("，,；;。")
    return duty.replace(name, "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析吉林省自然资源厅领导之窗和在线详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    organization = page_rule["organization"]
    base_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select('a[href*="/ldzc/"]'):
        name = re.sub(r"[\s\u00a0\u3000]+", "", link.get_text("", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(base_url, link.get("href", ""))
        same_host = urlparse(detail_url).netloc.lower() == urlparse(base_url).netloc.lower()
        real_person_page = bool(re.search(r"/jgzn/ldzc/.+/\d{6}/t\d+_\d+\.html$", urlparse(detail_url).path))
        if not (same_host and real_person_page):
            continue
        try:
            duty = _parse_detail_duty(_fetch_detail(detail_url), name)
        except Exception:
            duty = ""
        if not duty or re.search(r"(负责|分管|工作|简介)", duty):
            continue
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": "领导之窗链接+详情姓名前职务",
            }
        )
    return rows


if __name__ == "__main__":
    main()
