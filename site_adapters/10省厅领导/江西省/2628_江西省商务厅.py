from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2628',
 'page_type': '人物卡片页',
 'structure_group': 'jiangxi_commerce_current_org_leader_cards_v2',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'inline_parser_handles_fetch': True,
 'inline_fetch_collector': 'playwright',
 'extract_mode': 'list_direct',
 'collector': 'playwright',
 'parser': 'jiangxi_commerce_current_org_leader_cards_v2',
 'current_org_path': '/jxsswt/col/col35783/index.html',
 'leader_region_selector': '.container-r .ldbox',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.ld-xyp > a[href], .img-box > a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'candidate_links': []},
 'risk_flag': '规则表旧领导页已404；当前领导卡片迁至同站组织机构页，必须限定.container-r .ldbox以排除内设机构和新闻人物',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.container-r .ldbox',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.ld-xyp > a[href], .img-box > a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '当前组织机构页领导卡片DOM直接含姓名、职务和详情链接'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析江西省商务厅当前组织机构页中的领导卡片。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    del html
    current_url = urljoin(str(page_rule["url"]), str(page_rule["current_org_path"]))
    result = fetch_html_with_strategy(
        current_url,
        strategy="playwright",
        timeout=60,
        browser_render_wait_ms=2000,
    )
    soup = BeautifulSoup(result.html, "html.parser")
    leader_region = soup.select_one(str(page_rule["leader_region_selector"]))
    if leader_region is None:
        raise RuntimeError("当前组织机构页未找到领导信息区域")
    organization = str(page_rule["organization"])
    page_url = str(page_rule["url"])
    rows = []
    seen: set[str] = set()
    for link in leader_region.select(str(page_rule["detail_link_selector"])):
        text = " ".join(link.get_text(" ", strip=True).split())
        match = re.search(r"\s+(?P<name>[\u4e00-\u9fff](?:\s*[\u4e00-\u9fff]){1,3})$", text)
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = text[:match.start()].strip()
        if name in seen or not re.search(r"党组|厅长|会长|巡视员", duty):
            continue
        seen.add(name)
        detail_url = urljoin(result.final_url or final_url, link.get("href") or "")
        rows.append(
            {
                "organization": organization,
                "url": page_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule["parser"]),
                "selector_summary": "厅领导侧栏导航链接文本：职务+姓名",
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
