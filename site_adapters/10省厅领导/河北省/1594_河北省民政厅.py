from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urlsplit

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1594',
 'domain': 'minzheng.hebei.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_hebei_mz_api_ldfg_v1',
 'leader_region_selector': 'api:getItemByChannelPath path=ZZJG result.name=领导分工',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"browser_dom","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'div#layout > section.el-container.is-vertical > div > div.lay_padding '
                                               '> main.el-main.el-main-container',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': True, 'reason': '开放接口返回组织机构下领导分工contentList，标题含职务和姓名'},
             'migration': {'source': 'last_batch_online_template',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    page_url = str(page_rule.get("url", "")) or final_url
    parsed_url = urlsplit(page_url)
    api_url = f"{parsed_url.scheme}://{parsed_url.netloc}/cms/open/api/content/getItemByChannelPath"
    response = requests.get(api_url, params={"path": "ZZJG"}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    rows: list[dict] = []
    for item in payload.get("result", []):
        if item.get("name") != "领导分工":
            continue
        for content in item.get("contentList") or []:
            title = clean_text(content.get("title", ""))
            match = re.match(r"(.+?)\s+([\u4e00-\u9fa5]{2,4})$", title)
            if not match:
                continue
            duty = clean_text(match.group(1))
            name = match.group(2)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": "",
                    "evidence": duty,
                    "selector_summary": "接口领导分工contentList标题职务+姓名",
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
