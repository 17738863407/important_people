from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0849',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_shanxi_sasac_leader_links_v2',
 'leader_region_selector': "a[href*='/wld/']",
 'name_selector': '职务前缀前文本',
 'duty_selector': '省国资委或省纪委开头文本',
 'detail_link_selector': "a[href*='/wld/']",
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '委领导姓名可能含全角排版空格；只遍历href含/wld/的人物链接，并以省国资委或省纪委职务前缀拆分姓名和职务',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': "a[href*='/wld/']",
                     'name_selector': '职务前缀前文本',
                     'duty_selector': '省国资委或省纪委开头文本',
                     'detail_link_selector': "a[href*='/wld/']",
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'success_dir', 'behavior_changed': False}}}


def clean_text(value: str) -> str:
    """压缩半角、全角及不间断空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按委领导详情链接顺序拆分姓名和原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = final_url or str(page_rule.get("url") or "")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in soup.select("a[href*='/wld/']"):
        text = clean_text(link.get_text(" ", strip=True))
        boundary = re.search(r"省(?:国资委|纪委)", text)
        if boundary is None:
            continue
        name = re.sub(r"\s+", "", text[:boundary.start()])
        duty = clean_text(text[boundary.start():]).strip("。")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            raise RuntimeError(f"委领导姓名格式异常：{name or '<空>'}")
        if not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(source_url, str(link.get("href") or "")),
                "evidence": duty,
                "parser": "page_inline_shanxi_sasac_leader_links_v2",
                "selector_summary": "a[href*=/wld/]；省国资委或省纪委前缀拆分姓名职务",
            }
        )
    if not rows:
        raise RuntimeError("机构设置页未解析出委领导链接")
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
