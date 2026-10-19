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

PAGE_RULE = {'rule_id': '3413',
 'domain': 'zrzyt.hlj.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'parser': 'HeilongjiangNaturalResourcesLeaderCardParser_v1',
 'leader_region_selector': '.jgld_list > ul > li',
 'name_selector': 'h3.name',
 'duty_selector': '.jgld_info > .zw first',
 'detail_link_selector': 'a.ckxq[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.jgld_list > ul > li',
                     'name_selector': 'h3.name',
                     'duty_selector': '.jgld_info > .zw first',
                     'detail_link_selector': 'a.ckxq[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def _clean_text(text: str) -> str:
    text = (text or "").replace("\xa0", " ").replace("\u3000", " ")
    return " ".join(text.split())


def _clean_name(text: str) -> str:
    name = _clean_text(text).replace(" ", "")
    return re.sub(r"（[^）]*）|\([^)]*\)", "", name).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析黑龙江省自然资源厅机构领导卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for item in soup.select(".jgld_list > ul > li"):
        name_node = item.select_one("h3.name")
        duty_node = None
        for node in item.select(".jgld_info > .zw"):
            if "jl" not in (node.get("class") or []):
                duty_node = node
                break
        if name_node is None or duty_node is None:
            continue
        name = _clean_name(name_node.get_text(" ", strip=True))
        duty = _clean_text(duty_node.get_text(" ", strip=True)).replace("职务：", "").strip()
        if not name or not duty:
            continue
        link = item.select_one("a.ckxq[href]")
        detail_url = urldefrag(urljoin(base_url, link.get("href", ""))).url if link else ""
        parsed = urlsplit(detail_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or detail_url.rstrip("/") == base_url.rstrip("/"):
            detail_url = ""
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": "strategy=css；leader=.jgld_list > ul > li；name=h3.name；duty=.jgld_info>.zw去除职务标签；detail=a.ckxq[href]",
            }
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
