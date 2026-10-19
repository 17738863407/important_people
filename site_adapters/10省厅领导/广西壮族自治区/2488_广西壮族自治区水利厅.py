from __future__ import annotations

import sys
from pathlib import Path
import re
import urllib.request
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2488',
 'domain': 'slt.gxzf.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'custom_guangxi_water_leader_details_v1',
 'leader_region_selector': 'html > body > div.wrap.bg-white:nth-of-type(3)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
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
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > div.wrap.bg-white:nth-of-type(3)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'pending_root', 'behavior_changed': False}}}


def _clean_text(text: str) -> str:
    return " ".join(text.replace("\u3000", " ").replace("\xa0", " ").split())


def _fetch_detail_html(detail_url: str) -> str:
    request = urllib.request.Request(detail_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    return raw.decode(encoding, errors="replace")


def _extract_detail_duty(detail_html: str, name: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    content = soup.select_one(".trs_editor_view") or soup.select_one(".TRS_UEDITOR")
    text = _clean_text((content or soup).get_text(" ", strip=True))
    name_pattern = r"\s*".join(re.escape(char) for char in name)
    match = re.search(
        rf"{name_pattern}\s*同志\s*[：:]\s*(?P<evidence>自治区水利厅[^。]*。)",
        text,
    )
    if not match:
        return "", ""
    evidence = re.sub(r"[（(]兼[）)]", "", _clean_text(match.group("evidence")))
    evidence = re.sub(r"。$", "", evidence).strip("，、 ")
    return evidence.rstrip("。"), evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """在线解析广西壮族自治区水利厅领导目录及详情页。"""
    list_soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in list_soup.select("a[href]"):
        name = re.sub(r"\s+", "", _clean_text(link.get("title") or link.get_text(" ", strip=True)))
        href = link.get("href", "").strip()
        detail_url = urljoin(source_url, href)
        if (
            not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name)
            or not re.search(r"/ldxx/t\d+\.shtml(?:$|[?#])", detail_url)
            or name in seen
        ):
            continue
        try:
            duty, evidence = _extract_detail_duty(_fetch_detail_html(detail_url), name)
        except Exception:
            duty, evidence = "", ""
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": "custom_guangxi_water_leader_details_v1",
                "selector_summary": "领导目录姓名链接；详情正文姓名同志后自治区水利厅职务句",
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
