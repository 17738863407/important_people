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

PAGE_RULE = {'rule_id': '3349',
 'domain': 'www.zj.gov.cn',
 'page_type': '人物列表完整页',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'zhejiang_department_leader_card_parser_v1',
 'source_parser': 'zhejiang_department_leader_card_parser_v1',
 'leader_region_selector': 'body',
 'name_selector': '.ld_tit',
 'duty_selector': '.jg_ldxx_item.ldzw .txt_item',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复；已排除内设机构负责人混入风险',
 'confidence': 'low',
 'profile_reusable': '是',
 'profile_judgement': '网页画像通过_可用于该网页后续更新',
 'filter_policy': 'strong_no_wordlist'}


def clean_leader_duty(name: str, value: str) -> str:
    """保留领导现任职务，截断职责分工及其后的职责描述。"""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(rf"^{re.escape(name)}\s*", "", text)
    text = re.split(r"\s*职责分工\s*[：:]", text, maxsplit=1)[0]
    return text.strip(" \t，,。；;")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """抽取浙江部门领导卡片，并仅保留可验证的现任职务。"""
    from crawler_core.parsers_v1 import zhejiang_department_leader_card_parser_v1

    records = zhejiang_department_leader_card_parser_v1(page_rule, html, final_url)
    homepage_url = urljoin(final_url, "/index.html")
    for record in records:
        cleaned_duty = clean_leader_duty(record.name, record.evidence or record.duty)
        record.duty = cleaned_duty
        record.evidence = cleaned_duty
        if record.detail_url in {final_url, homepage_url}:
            record.detail_url = ""
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
