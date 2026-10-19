from __future__ import annotations

import re
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
    "rule_id": "3957",
    "domain": "yjszx.gov.cn",
    "page_type": "职务标题与人物图片表格",
    "structure_group": "yangjiang_cppcc_grouped_image_tables",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_yangjiang_cppcc_tables_v1",
    "leader_region_selector": "#zoomcon",
    "name_selector": "table td:has(img)",
    "duty_selector": "table",
    "content_scope": {"include_selectors": ["#zoomcon"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "职务标题表与人物图片表交替，人物表含大量空单元格，须按表格DOM顺序继承职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": "#zoomcon", "table_selector": ":scope > table"},
        "record_boundary": "仅含图片的单元格；职务由此前最近的主席、副主席、秘书长标题表继承",
        "api": {"enabled": False, "reason": "静态正文表格已直接包含职务标题和人物姓名"},
    },
}


def compact_text(value: str) -> str:
    """删除表格字段中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """依次处理标题表和人物图片表，保持表格行列原序。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#zoomcon")
    if region is None:
        raise RuntimeError("未找到政协领导正文 #zoomcon")
    rows: list[dict[str, str]] = []
    current_duty = ""
    for table in region.select(":scope > table"):
        table_text = compact_text(table.get_text(" ", strip=True))
        if table_text in {"主席", "副主席", "秘书长"}:
            current_duty = table_text
            continue
        if not current_duty:
            continue
        for cell in table.select("td"):
            if cell.select_one("img") is None:
                continue
            candidates = [compact_text(value) for value in cell.stripped_strings]
            names = [value for value in candidates if re.fullmatch(r"[\u3400-\u9fff·]{2,4}", value)]
            if not names:
                continue
            rows.append(
                {
                    "name": names[-1],
                    "duty": current_duty,
                    "evidence": current_duty,
                    "detail_url": "",
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": "#zoomcon直属标题表与随后人物图片表；含图单元格",
                }
            )
    if not rows:
        raise RuntimeError("政协领导图片表格未解析出有效人物")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
