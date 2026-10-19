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

PAGE_RULE = {'rule_id': '1593',
 'domain': 'www.minge.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'raw_http',
 'extract_mode': 'custom',
 'collector': 'raw_http',
 'parser': 'custom_minge_leader_detail_resume_v1',
 'leader_region_selector': '.mg-introductor-wrap-fr a',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > div.mg-introductor-container.clearfix:nth-of-type(7)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线列表含姓名链接，在线详情含现任句'},
             'migration': {}}}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_evidence(text: str) -> str:
    """删除详情页完整现任句的固定标签与纯句末句号。"""
    value = re.sub(r"^现任\s*", "", clean_text(text))
    return value[:-1].rstrip() if value.endswith("。") else value


def load_detail_duty(detail_url: str) -> str:
    response = requests.get(detail_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    text = clean_text(soup.get_text(" ", strip=True))
    match = re.search(r"现任[^。]*。", text)
    return clean_evidence(match.group(0)) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for link in soup.select(".mg-introductor-wrap-fr a[href]"):
        name = clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
            continue
        detail_url = urljoin(final_url, link.get("href", ""))
        duty = load_detail_duty(detail_url)
        if not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "selector_summary": "领导介绍姓名链接+详情现任句",
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
