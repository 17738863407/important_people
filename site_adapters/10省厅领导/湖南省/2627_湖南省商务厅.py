from __future__ import annotations

import sys
from pathlib import Path
import re
from urllib.parse import urljoin
from urllib.request import Request, urlopen


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2627',
 'domain': 'swt.hunan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'hunan_commerce_list_detail_v1',
 'leader_region_selector': '厅领导信息列表及详情页职务字段',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'list_to_detail'},
 'risk_flag': '页面包含iframe',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.main1400.clear_both:nth-of-type(3) > div.djgg > '
                                               'div.djgg_wznr > div.leaderxx:nth-of-type(3)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '列表页仅姓名日期，详情页含职务字段'},
             }}


def _extract_text(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", "\n", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    return re.sub(r"\n{2,}", "\n", text).strip()


def parse_page(html: str, page_url: str, page_rule: dict):
    """湖南省商务厅列表页只有姓名日期，职务从在线详情页补齐。"""
    rows = []
    for match in re.finditer(r'href="([^"]*jgldg/[^"]*t20[^"]+\.html)"[^>]*title="([\u4e00-\u9fa5]{2,4})"', html):
        detail_url = urljoin(page_url, match.group(1))
        name = match.group(2)
        try:
            with urlopen(Request(detail_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20) as response:
                detail_html = response.read().decode("utf-8", errors="ignore")
        except Exception:
            continue
        detail_text = _extract_text(detail_html)
        duty_match = re.search(r"职\s*务[：:]\s*([^\n]+)", detail_text)
        if not duty_match:
            continue
        duty = duty_match.group(1).strip()
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": "列表页姓名日期链接 + 详情页职务字段",
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
