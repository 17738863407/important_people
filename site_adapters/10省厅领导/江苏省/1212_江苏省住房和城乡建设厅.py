from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")



PAGE_RULE = {'rule_id': '1212',
 'domain': 'jsszfhcxjst.jiangsu.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_jiangsu_housing_online_detail_xianren_v3',
 'inline_parser_handles_fetch': True,
 'inline_fetch_collector': 'playwright',
 'risk_flag': '入口本身也是首位人物专属栏目，须保留其人物且详情链接留空；按左侧目录原序逐页读取简介现职句，保留机构全称',
 'leader_region_selector': 'ul.szlb a[href]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 0},
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'ul.szlb a[href]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'}}}


def normalize_space(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """姓名内部不保留排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def clean_duty(value: str) -> str:
    """仅清理排版和句末标点，保留网页明确给出的机构主体。"""
    duty = normalize_space(value).rstrip("。")
    return duty


def load_detail_html(detail_url: str, referer: str) -> str:
    """在线获取领导详情栏目页 HTML。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    return fetch_html_with_strategy(
        detail_url, strategy="playwright", timeout=35, browser_render_wait_ms=1000
    ).html


def extract_duty_from_detail(detail_html: str, name: str) -> tuple[str, str]:
    """从详情页简介段“现任……”句提取职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()
    scope = soup.select_one(".fg-x")
    if scope is None:
        raise RuntimeError("人物简介区域缺失")
    lines = [normalize_space(line) for line in scope.get_text("\n", strip=True).splitlines()]
    for line in lines:
        if name not in clean_name(line) or "现任" not in line:
            continue
        match = re.search(r"现任(.+?)(?:。|$)", line)
        if not match:
            continue
        evidence_match = re.search(r"现任[^。]*。", line)
        evidence = evidence_match.group(0) if evidence_match else f"现任{match.group(1).rstrip('。')}。"
        evidence = re.sub(r"^现任\s*", "", normalize_space(evidence)).rstrip("。 ")
        return clean_duty(match.group(1)), evidence
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析江苏省住房和城乡建设厅领导目录，并在线读取详情页补全职务。"""
    html = load_detail_html(str(page_rule["url"]), str(page_rule["url"]))
    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", "")) or final_url
    parser = str(page_rule.get("parser", ""))
    selector_summary = (
        "strategy=custom_parse_page；selector=ul.szlb a[href]；"
        "detail=online column page；field=.fg-x text contains 现任"
    )
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select("ul.szlb a[href]"):
        name = clean_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(page_url, link.get("href", ""))
        detail = urlparse(detail_url)
        source = urlparse(page_url)
        if (
            detail.scheme not in {"http", "https"}
            or detail.netloc.lower() != source.netloc.lower()
            or detail.fragment
            or not re.search(r"/col/col\d+(?:/index\.html)?/?$", detail.path)
        ):
            continue
        is_entry = detail.path.rstrip("/") == source.path.rstrip("/")
        detail_html = html if is_entry else load_detail_html(detail_url, page_url)
        duty, evidence_text = extract_duty_from_detail(detail_html, name)
        if not duty:
            raise RuntimeError(f"人物简介未找到可回指的现职句：{name}")
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": page_url,
                "name": name,
                "duty": duty,
                "detail_url": "" if is_entry else detail_url,
                "evidence": evidence_text,
                "parser": parser,
                "selector_summary": selector_summary,
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
