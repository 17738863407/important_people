from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1243',
 'domain': 'jtt.hubei.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_inline_hubei_transport_leader_h4_cards_v1',
 'leader_region_selector': '.leader ul.list-p li',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.leader ul.list-p li a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '领导卡片h4内姓名职务换行分隔，旧body文本解析漏人；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.leader ul.list-p li',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.leader ul.list-p li a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '当前脚本缺少可复现 api 配置，沿用在线 DOM 定位'}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(rule.get("url", ""))
    rows = []
    seen = set()
    for item in soup.select(".leader ul.list-p li"):
        title = item.select_one("h4")
        link = item.select_one("a[href]")
        if not title:
            continue
        parts = [clean_text(part) for part in title.get_text("\n", strip=True).splitlines()]
        parts = [part for part in parts if part]
        if len(parts) < 2:
            continue
        name = parts[0].replace(" ", "")
        duty = clean_text(" ".join(parts[1:]))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue
        if not re.search(r"书记|厅长|局长|成员|监察组", duty):
            continue
        detail_url = urldefrag(urljoin(base_url, link.get("href", ""))).url if link else ""
        parsed = urlsplit(detail_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or detail_url.rstrip("/") == base_url.rstrip("/"):
            detail_url = ""
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "organization": str(rule.get("organization", "")),
                "url": base_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(rule.get("parser", "")),
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
