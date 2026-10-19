from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4251",
    "page_type": "领导简介段落",
    "structure_group": "国家能源局河南监管办公室领导信息正文",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_nea_henan_leaders_v1",
    "leader_region_selector": ".view.TRS_UEDITOR",
    "name_selector": "p",
    "duty_selector": "当前人物段落中的现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文段落包含简历信息，必须只从同一段落的现任句提取职务。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析逐人简介段落中的姓名与完整现任句。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select(".view.TRS_UEDITOR p"):
        text = re.sub(r"\s+", "", paragraph.get_text(" ", strip=True))
        matched = re.fullmatch(r"([\u4e00-\u9fff·]{2,8})，.*?现任(.+?)。", text)
        if not matched:
            continue
        name, duty = matched.groups()
        if name in seen or not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": ".view.TRS_UEDITOR逐人简介段落中的现任句",
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
