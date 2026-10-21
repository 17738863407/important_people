from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """仅从权威领导成员列表抽取；列表未发布条目时明确失败。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".main ul.aclist")
    if not scope:
        raise RuntimeError("权威领导成员入口缺少列表容器：.main ul.aclist")
    items = scope.select(":scope > li")
    if not items:
        raise RuntimeError("权威领导成员入口在线正文为空：ul.aclist 未发布领导条目")
    rows: list[dict[str, str]] = []
    for item in items:
        name_node = item.select_one(".name, h3, h4, h5, h6")
        duty_node = item.select_one(".duty, .position, p")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = re.sub(r"\s+", " ", duty_node.get_text(" ", strip=True)).strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "medium",
                "parser": "page_inline_regcc_authoritative_list_v2",
            }
        )
    if not rows:
        raise RuntimeError("权威领导成员列表存在条目，但未发现可验证的姓名—职务字段结构")
    return rows


PAGE_RULE = {'rule_id': '3544',
 'page_type': '人物列表完整页',
 'structure_group': 'regcc_authoritative_leader_list',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'field_pair',
 'collector': 'static_http',
 'parser': 'page_inline_regcc_authoritative_list_v2',
 'leader_region_selector': '.main ul.aclist > li',
 'name_selector': '.name, h3, h4, h5, h6',
 'duty_selector': '.duty, .position, p',
 'detail_link_selector': '',
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_link_selector': None},
 'risk_flag': '权威入口当前列表为空，禁止新闻报道或历史结果兜底',
 'confidence': 'medium',
 'configuration_status': '在线核验：当前权威列表为空'}

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
