from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0973",
    "page_type": "人物列表完整页",
    "structure_group": "haikou_civil_affairs_name_duty_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".TRS_UEDITOR",
    "name_selector": ".TRS_UEDITOR p姓名标签段落",
    "duty_selector": "当前姓名后的职务标签段落",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "姓名：",
        "end_anchor": "",
        "include_selectors": [".TRS_UEDITOR"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "页面实际为头像后姓名与职务连续段落，须在下一姓名前配对并排除空段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".TRS_UEDITOR")
    if content is None:
        raise ValueError("页面未发现领导信息正文容器.TR S_UEDITOR")
    rows: list[dict[str, str]] = []
    current_name = ""
    for paragraph in content.select("p"):
        text = compact_text(paragraph.get_text(" ", strip=True))
        name_match = re.fullmatch(r"姓名[：:](?P<name>[\u3400-\u9fff·]{2,12})", text)
        if name_match:
            current_name = name_match.group("name")
            continue
        duty_match = re.fullmatch(r"职务[：:](?P<duty>.+)", text)
        if not duty_match or not current_name:
            continue
        duty = duty_match.group("duty")
        rows.append(
            {
                "name": current_name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": ".TRS_UEDITOR当前姓名标签后的职务标签段落",
            }
        )
        current_name = ""
    if not rows:
        raise ValueError("领导正文未发现可配对的姓名与职务标签段落")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
