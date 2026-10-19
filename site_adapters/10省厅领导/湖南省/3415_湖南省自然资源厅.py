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

PAGE_RULE = {'rule_id': '3415',
 'domain': 'zrzyt.hunan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'page_detail_online_hunan_natural_resources_leader_v1',
 'leader_region_selector': '.leader-cp-gl a[href]',
 'name_selector': '领导卡片链接文本',
 'duty_selector': '详情页职务字段',
 'detail_link_selector': '.leader-cp-gl a[href]',
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
 'risk_flag': '页面包含iframe',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.container:nth-of-type(3) > '
                                               'div.main_list_right:nth-of-type(3) > div.leader-cp-gl',
                     'name_selector': '领导卡片链接文本',
                     'duty_selector': '详情页职务字段',
                     'detail_link_selector': '.leader-cp-gl a[href]',
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


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value).strip()


def _extract_duty(detail_html: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    for item in soup.select(".jdld_leader_zw"):
        text = _clean_text(item.get_text(" ", strip=True)).replace("职 务", "职务")
        match = re.search(r"职\s*务[:：]\s*(.+)$", text)
        if match:
            duty = match.group(1).strip().rstrip("，,；;。")
            if duty and not duty.startswith("工作职责"):
                return duty, text

    text = _clean_text(soup.get_text(" ", strip=True)).replace("职 务", "职务")
    match = re.search(r"职\s*务[:：]\s*(.+?)\s*工作职责", text)
    if match:
        duty = match.group(1).strip().rstrip("，,；;。")
        return duty, f"职务：{duty}"
    return "", text[:120]


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


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析湖南省自然资源厅机构领导列表及在线详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = page_rule["organization"]
    base_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".leader-cp-gl a[href]"):
        name = _clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        href = link.get("href", "")
        detail_url = urljoin(base_url, href)
        if urlparse(detail_url).netloc.lower() != urlparse(base_url).netloc.lower():
            continue
        if not re.search(r"/jgld/\d{6}/t\d+_\d+\.html$", urlparse(detail_url).path):
            continue
        duty, _ = _extract_duty(_fetch_detail(detail_url))
        if not duty:
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
                "selector_summary": ".leader-cp-gl名单 + 在线详情职务字段",
            }
        )
    return rows


if __name__ == "__main__":
    main()
