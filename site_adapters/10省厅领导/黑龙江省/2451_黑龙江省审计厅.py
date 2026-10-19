from __future__ import annotations

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

PAGE_RULE = {'rule_id': '2451',
 'domain': 'sjt.hlj.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'parser': 'V004_card_person_v1',
 'leader_region_selector': 'html > body > div.container:nth-of-type(2) > div.row.jgld_mainContent:nth-of-type(2)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > div.container:nth-of-type(2) > '
                                               'div.row.jgld_mainContent:nth-of-type(2)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def _clean_text(text: str) -> str:
    return " ".join(text.replace("\u3000", " ").split())


def _clean_name(text: str) -> str:
    return "".join(text.replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析黑龙江省审计厅机构领导列表卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    source_url = str(page_rule.get("url", final_url))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(".jgld_list li"):
        name_node = item.select_one("h3.name")
        duty_node = item.select_one(".jgld_info > .zw")
        if not name_node or not duty_node:
            continue
        name = _clean_name(name_node.get_text(" ", strip=True))
        duty = _clean_text(duty_node.get_text(" ", strip=True).replace("职务：", "", 1))
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        link = item.select_one("a.ckxq[href]") or item.select_one("a[href]")
        href = link.get("href", "").strip() if link else ""
        detail_url = urldefrag(urljoin(final_url or source_url, href)).url if href else ""
        parsed = urlsplit(detail_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or detail_url.rstrip("/") == source_url.rstrip("/"):
            detail_url = ""
        rows.append(
            {
                "organization": organization,
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_heilongjiang_audit_card_v1",
                "selector_summary": ".jgld_list li；h3.name + .zw + a.ckxq",
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
