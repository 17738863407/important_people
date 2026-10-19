from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2047',
 'domain': 'nynct.henan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'parser': 'custom_henan_nynct_list_detail_v1',
 'leader_region_selector': '.zwxxgk_bd a[href*="/20"]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True, 'mode': 'person_name_link'},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.zwxxgk_bd a[href*="/20"]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '列表姓名链接+在线详情现任职务'}}}


def clean_text(text: str) -> str:
    return " ".join((text or "").replace("\xa0", " ").split())


def extract_duty(name: str, detail_html: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    text = clean_text(soup.get_text(" ", strip=True))
    match = re.search(r"现任(.+?)。", text)
    if match:
        duty = clean_text(match.group(1).strip(" ，,"))
        return duty, duty
    share_text = text.split("分享：", 1)[1] if "分享：" in text else text
    marker = name + "，"
    if marker in share_text:
        duty = clean_text(share_text.split(marker, 1)[0].strip(" ，,"))
        return duty, duty
    return "", ""


def fetch_detail_html(url: str) -> str:
    """在线读取领导详情页，单页失败由调用方跳过。"""
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    page_url = final_url or str(page_rule.get("url", ""))
    rows = []
    seen_names = set()
    for link in soup.select('.zwxxgk_bd a[href*="/20"]'):
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen_names:
            continue
        detail_url = urldefrag(urljoin(page_url, str(link.get("href", "")).strip())).url
        parsed = urlsplit(detail_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or detail_url.rstrip("/") == page_url.rstrip("/"):
            continue
        try:
            duty, evidence = extract_duty(name, fetch_detail_html(detail_url))
        except Exception:
            continue
        if not duty:
            continue
        seen_names.add(name)
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": detail_url,
            "evidence": evidence,
            "selector_summary": "列表姓名链接+详情现任职务",
        })
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
