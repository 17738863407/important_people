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
    "rule_id": "3953",
    "domain": "www.smxzxw.gov.cn",
    "page_type": "人物图片表格",
    "structure_group": "sanmenxia_cppcc_image_table",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_sanmenxia_cppcc_table_v1",
    "leader_region_selector": ".rightBox .content table",
    "name_selector": "td",
    "duty_selector": "td",
    "content_scope": {"include_selectors": [".rightBox .content table"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物单元格由图片、姓名和职务换行组成，且末行含空单元格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".rightBox .content table", "record_selector": "td"},
        "field_order": "单元格非空文本第一项姓名、其余项职务",
        "api": {"enabled": False, "reason": "静态HTML表格已直接包含姓名和现职"},
    },
}


def normalize_text(value: str) -> str:
    """删除字段中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按表格行列顺序读取每个人物单元格中的姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one(".rightBox .content table")
    if table is None:
        raise RuntimeError("未找到政协领导人物表格")
    rows: list[dict[str, str]] = []
    record_pattern = re.compile(
        r"^([\u3400-\u9fff·]{2,4}?)((?:党组书记|党组成员|主席|副主席|秘书长).*)$"
    )
    for cell in table.select("td"):
        text = normalize_text(cell.get_text(" ", strip=True))
        match = record_pattern.fullmatch(text)
        if not match:
            continue
        name, duty = match.groups()
        if not re.search(r"主席|秘书长", duty):
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".rightBox .content table单元格非空文本顺序",
            }
        )
    if not rows:
        raise RuntimeError("政协领导人物表格未解析出有效记录")
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
