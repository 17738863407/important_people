from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1779',
 'domain': 'mzt.gxzf.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'guangxi_mzt_leader_directory_detail_v1',
 'leader_region_selector': '.gov-leader-list li a',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.gov-leader-list li a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
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
 'locator': {'css': {'leader_region_selector': 'body',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': "a[href*='ld']",
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'pending_root', 'behavior_changed': False}}}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def _clean_duty(text: str) -> str:
    text = _clean_text(text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"\s*([、，,；;：:（）()])\s*", r"\1", text)
    return text


def _fetch_detail_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        body = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    return body.decode(encoding, errors="replace")


def _extract_duty(detail_html: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    text = _clean_text(soup.get_text(" ", strip=True))
    match = re.search(r"现任(.+?)。", text)
    if match:
        duty = _clean_duty(match.group(1)).replace("（兼）", "").replace("(兼)", "").strip()
        return duty, duty

    edition = soup.select_one("#NewsEditionName")
    if edition:
        evidence = _clean_text(edition.get_text(" ", strip=True))
        return evidence, evidence
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析广西壮族自治区民政厅领导目录，并从详情页抽取完整现任职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records = []
    seen_names: set[str] = set()

    for link in soup.select(".gov-leader-list li a[href]"):
        name_node = link.select_one("span")
        name = _clean_text(name_node.get_text(" ", strip=True) if name_node else link.get_text(" ", strip=True))
        if not name or name in seen_names:
            continue
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue

        detail_url = urljoin(page_rule["url"], link.get("href", ""))
        duty, evidence = _extract_duty(_fetch_detail_html(detail_url))
        if not duty:
            continue

        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="list=.gov-leader-list li a; detail=text regex 现任(.+?)。",
            )
        )

    return records


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
