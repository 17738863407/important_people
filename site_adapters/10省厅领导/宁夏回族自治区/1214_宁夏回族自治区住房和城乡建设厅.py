from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1214',
 'domain': 'jst.nx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_ningxia_housing_local_detail_org_duty_v1',
 'leader_region_selector': "a[href*='/ldjj/']",
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 0},
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': "a[href*='/ldjj/']",
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'}}}


def normalize_space(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """姓名内部不保留排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def clean_duty(value: str) -> str:
    """清理机构名前缀后的职务文本。"""
    duty = normalize_space(value).strip(" ，。")
    duty = re.sub(r"[（(]\s*挂职\s*[）)]", "", duty)
    return re.sub(r"\s*、\s*", "、", duty)


def extract_duty_from_detail(detail_html: str, organization: str) -> tuple[str, str]:
    """从详情页正文中按机构名截取职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    content = soup.select_one("article .view") or soup.select_one(".view")
    if not content:
        return "", ""
    text = normalize_space(content.get_text(" ", strip=True))
    index = text.find(organization)
    if index < 0:
        return "", text
    after = text[index + len(organization):]
    stop = re.search(r"[，。]\s*(?:男|女)[，、]", after)
    if stop:
        duty = after[: stop.start()]
    else:
        duty = re.split(r"[。]", after, maxsplit=1)[0]
    return clean_duty(duty), text


def load_detail_html(detail_url: str, referer: str) -> str:
    """在线读取领导详情页。"""
    session = requests.Session()
    session.trust_env = False
    response = session.get(
        detail_url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": referer},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.text


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析宁夏回族自治区住房和城乡建设厅领导目录，并在线读取详情页补全职务。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", "")) or final_url
    parser = str(page_rule.get("parser", ""))
    selector_summary = (
        "strategy=custom_parse_page；selector=a[href*='/ldjj/']；"
        "detail=online detail；field=article .view contains 机构名"
    )
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select("a[href*='/ldjj/']"):
        name = clean_name(link.get_text(" ", strip=True))
        if name == "领导简介" or not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        detail_fetch_url = urljoin(page_url, link.get("href", ""))
        detail = urlparse(detail_fetch_url)
        source = urlparse(page_url)
        if (
            detail.scheme not in {"http", "https"}
            or detail.netloc.lower() != source.netloc.lower()
            or detail.fragment
            or "/ldjj/" not in detail.path
            or not re.search(r"/ldjj/[^/]+/$", detail.path)
        ):
            continue
        detail_url = (
            "" if detail.path.rstrip("/") == source.path.rstrip("/") else detail_fetch_url
        )
        duty, _ = extract_duty_from_detail(load_detail_html(detail_fetch_url, page_url), organization)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": page_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
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
