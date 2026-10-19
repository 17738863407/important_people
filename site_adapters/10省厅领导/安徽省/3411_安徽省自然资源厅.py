from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3411',
 'domain': 'zrzyt.ah.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_leader_box_anhui_natural_resources_leader_v1',
 'leader_region_selector': '.ls-gyy-ldbox a[href]',
 'name_selector': '链接文本开头姓名',
 'duty_selector': '链接文本姓名后职务',
 'detail_link_selector': '.ls-gyy-ldbox a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.ls-gyy-ldbox a[href]',
                     'name_selector': '链接文本开头姓名',
                     'duty_selector': '链接文本姓名后职务',
                     'detail_link_selector': '.ls-gyy-ldbox a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用既有 CSS/HTML 定位解析'}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析安徽省自然资源厅领导介绍链接文本。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".ls-gyy-ldbox a[href]"):
        text = re.sub(r"[\s\u00a0\u3000]+", " ", link.get_text(" ", strip=True)).strip()
        match = re.match(r"^([\u4e00-\u9fa5]\s*[\u4e00-\u9fa5]{1,3})\s+(.+)$", text)
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group(1))
        duty = re.sub(r"\s+", "", match.group(2)).rstrip("，,；;。")
        if name in seen or not re.search(r"(党组|厅长|政治部主任|测绘)", duty):
            continue
        seen.add(name)
        href = str(link.get("href") or "").strip()
        detail_url = ""
        if href and not href.lower().startswith(("#", "javascript:")):
            candidate_url = urljoin(base_url, href)
            if candidate_url.rstrip("/") != base_url.rstrip("/"):
                detail_url = candidate_url
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": ".ls-gyy-ldbox链接文本",
            }
        )
    return rows


if __name__ == "__main__":
    main()
