from __future__ import annotations

import re
import sys
from urllib.parse import urldefrag, urljoin, urlsplit
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2570',
 'domain': 'sthjt.henan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'parser': 'custom_henan_ecology_leader_title_v1',
 'leader_region_selector': '.main领导信息列表',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': 'html > body > div.wrap:nth-of-type(1)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '领导信息列表标题直接包含姓名和职务'}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one(".main") or soup
    rows: list[dict] = []
    seen: set[str] = set()
    pattern = re.compile(r"^河南省生态环境厅(?P<duty>.+?)(?P<name>[\u4e00-\u9fff]{2,3})简历$")
    for link in main.find_all("a", href=True):
        title = _clean_text(link.get_text(" ", strip=True))
        match = pattern.match(title)
        if not match:
            continue
        name = match.group("name")
        duty = _clean_text(match.group("duty"))
        if name.startswith("长") and duty.endswith("副厅"):
            duty = f"{duty}长"
            name = name[1:]
        if name in seen:
            continue
        seen.add(name)
        detail_url = urldefrag(urljoin(page_rule["url"], link.get("href") or "")).url
        parsed = urlsplit(detail_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or detail_url.rstrip("/") == page_rule["url"].rstrip("/"):
            detail_url = ""
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_henan_ecology_leader_title_v1",
                "selector_summary": ".main列表标题：机构+职务+姓名+简历",
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
