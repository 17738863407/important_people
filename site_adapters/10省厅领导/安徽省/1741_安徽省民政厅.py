from __future__ import annotations

import sys
import re
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

PAGE_RULE = {'rule_id': '1741',
 'domain': 'mz.ah.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'custom_anhui_mz_list_detail_v1',
 'leader_region_selector': 'a.title[href*="/public/21761/"]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none'},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'a.title[href*="/public/21761/"]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线列表页含领导姓名，在线详情页含现任职务'}}}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def extract_detail(name: str, detail_url: str) -> tuple[str, str]:
    if not detail_url:
        return "", ""
    try:
        response = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        response.raise_for_status()
    except requests.RequestException:
        return "", ""
    response.encoding = response.apparent_encoding or "utf-8"
    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one(".gk_content") or soup.select_one(".xxgk_content") or soup.body
    text = clean_text(node.get_text(" ", strip=True) if node else "")
    if name in text:
        text = text[text.rfind(name, 0, text.find("现任") if "现任" in text else len(text)) + len(name):]
    match = re.search(r"现任(.+?)(?:，?\s*主持|，?\s*分管|。|联系方式)", text)
    duty = clean_text(match.group(1)) if match else ""
    duty = re.sub(r"\s*([、，])\s*", r"\1", duty).rstrip("，。")
    return duty, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()
    source_url = final_url or str(page_rule.get("url", ""))
    for link in soup.select('a.title[href*="/public/21761/"]'):
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        href = str(link.get("href") or "").strip()
        if not href or href.lower().startswith(("#", "javascript:")):
            continue
        detail_url = urljoin(source_url, href)
        if detail_url.rstrip("/") == source_url.rstrip("/"):
            continue
        duty, evidence_text = extract_detail(name, detail_url)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence_text,
                "selector_summary": "列表a.title姓名+详情页现任后职务",
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
