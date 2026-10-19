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

PAGE_RULE = {'rule_id': '2826',
 'domain': 'tyjrswt.hunan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'hunan_veterans_detail_duty_field_v1',
 'leader_region_selector': '机构领导列表及详情页职务字段',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'list_to_detail'},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': 'html > body > div.i-main:nth-of-type(2)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '列表页含领导姓名，详情页正文含职务字段'},
             }}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _fetch_detail(detail_url: str) -> str:
    """在线读取详情；该站 HTTPS 偶发椭圆曲线握手错误，失败时兼容 HTTP。"""
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


def _extract_duty(detail_html: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    text = _clean_text(soup.get_text(" ", strip=True))
    match = re.search(r"职\s*务[：:]\s*(.+?)\s*工作职责[：:]", text)
    return _clean_text(match.group(1)) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按原机构领导区域顺序取姓名链接，并从在线详情页读取职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("html > body > div.i-main:nth-of-type(2)")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    if region is None:
        return rows
    for link in region.select("a[href]"):
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        href = link.get("href") or ""
        if not re.search(r"/c100260/\d{6}/t\d+_\d+\.html$", href):
            continue
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, href)
        if urlparse(detail_url).netloc.lower() != urlparse(final_url).netloc.lower():
            continue
        duty = _extract_duty(_fetch_detail(detail_url))
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": str(page_rule["organization"]),
                "url": str(page_rule["url"]),
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule["parser"]),
                "selector_summary": "原 i-main 机构领导区域姓名链接；详情页职务字段",
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
