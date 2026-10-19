from __future__ import annotations

import sys
import re
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3237',
 'domain': 'yjt.ah.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'anhui_emergency_management_leader_list_v1',
 'leader_region_selector': 'html > body.lmbodybg > div.wza-container:nth-of-type(1)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none'},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body.lmbodybg > div.wza-container:nth-of-type(1)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线机构领导区域直接列姓名和职务'}}}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """安徽省应急管理厅机构领导列表直接列出姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("html > body.lmbodybg > div.wza-container:nth-of-type(1)")
    if not region:
        return []
    parser = str(page_rule.get("parser", ""))
    selector_summary = "机构领导列表条目：姓名：职务"
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_line in region.get_text("\n", strip=True).splitlines():
        line = " ".join(raw_line.replace("\u3000", " ").split())
        match = re.match(r"^(?P<name>[\u4e00-\u9fa5·]{2,4})\s*[：:]\s*(?P<duty>.+)$", line)
        if not match:
            continue
        name = match.group("name")
        duty = match.group("duty").strip()
        if name in seen or not re.search(r"厅长|副厅长|党委|书记|组长|总工程师|巡视员|主任", duty):
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
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
