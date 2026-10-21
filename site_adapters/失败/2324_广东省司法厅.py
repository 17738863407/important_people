from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2324',
 'domain': 'sft.gd.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'custom_gd_sft_gkmlpt_detail_colon_v1',
 'leader_region_selector': '#postList a.document-number',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '#postList a.document-number',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线动态页面使用 CSS/HTML 定位并逐详情解析'}}}


def clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def normalize_url(href: str, base_url: str) -> str:
    if href.startswith("//"):
        return "http:" + href
    return urljoin(base_url, href)


def extract_detail_duty(detail_url: str, name: str) -> tuple[str, str]:
    try:
        response = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        response.raise_for_status()
    except requests.RequestException:
        return "", ""
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, "html.parser")
    for paragraph in soup.find_all("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if "：" not in text or name not in text:
            continue
        left, right = text.rsplit("：", 1)
        if clean_text(right) == name and left:
            return clean_text(left), text
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()

    for link in soup.select("#postList a.document-number[href]"):
        name = clean_text(link.get_text(" ", strip=True))
        if not name or name in seen:
            continue
        href = str(link.get("href") or "").strip()
        if not href or href.lower().startswith(("#", "javascript:")):
            continue
        detail_url = normalize_url(href, final_url or page_rule["url"])
        if detail_url.rstrip("/") == (final_url or page_rule["url"]).rstrip("/"):
            detail_url = ""
        if not detail_url:
            continue
        duty, evidence = extract_detail_duty(detail_url, name)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "selector_summary": "#postList姓名链接+详情职务冒号姓名",
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
