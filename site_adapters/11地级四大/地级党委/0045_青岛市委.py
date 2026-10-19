from __future__ import annotations

import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0045",
    "page_type": "百度百科半结构领导栏目",
    "load_mode": "动态DOM渲染",
    "extraction_mode": "半结构分组解析",
    "parser": "S027_baidu_baike_leader_section_v1",
    "locator_strategy": "custom_parse_page",
    "baike_section_titles": ["市委领导"],
    "confidence": "高",
    "risk_notes": "目标栏目不存在时必须失败，禁止回退解析百科全文；仅解析指定现任领导栏目。",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list:
    """确认目标栏目真实存在后，再调用已注册的百科领导栏目解析器。"""
    soup = BeautifulSoup(html or "", "html.parser")
    expected_titles = {
        "".join(str(title).split()) for title in page_rule.get("baike_section_titles", [])
    }
    matched_headers = []
    for header in soup.select('.J-lemma-content div[data-tag="header"][data-level]'):
        title = "".join(
            str(header.get("data-name") or header.get_text(" ", strip=True)).split()
        )
        if title in expected_titles:
            matched_headers.append(header)
    if len(matched_headers) != 1:
        raise RuntimeError(f"目标领导栏目数量异常：{len(matched_headers)}")

    from crawler_core.baidu_baike import parse_baidu_baike_leader_section_v1

    rows = parse_baidu_baike_leader_section_v1(page_rule, html, final_url, None)
    if not rows:
        raise RuntimeError("目标领导栏目没有可验证的人物记录")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

