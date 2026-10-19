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
    "rule_id": "2877",
    "domain": "whlyj.beijing.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "beijing_culture_introduce_titles_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_beijing_culture_introduce_titles_v1",
    "risk_flag": "姓名内部与姓名职务边界均使用全角空格；按短姓名与北京市职务起点分离",
    "confidence": "high",
    "locator_strategy": "custom_parse_page",
}


def compact_text(value: str) -> str:
    """移除中文标题中的排版空白。"""
    return re.sub(r"\s+", "", str(value or "").replace("\u200b", ""))


def split_heading(value: str) -> tuple[str, str]:
    """从全角空格标题中识别姓名和以北京市开头的原始职务。"""
    match = re.fullmatch(
        r"(?P<name>(?:[\u4e00-\u9fff·][\u3000 ]*){2,4}?)[\u3000 ]+(?P<duty>北京市.+)",
        str(value or "").strip(),
    )
    if match is None:
        return "", ""
    return compact_text(match.group("name")), compact_text(match.group("duty"))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按文化和旅游局人物标题的DOM原始顺序解析。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for node in soup.select(".piclist .introduce h1"):
        name, duty = split_heading(node.get_text(" ", strip=True))
        if not name or not duty:
            continue
        evidence = duty.replace("（挂职）", "").replace("(挂职)", "").strip(" ，,。；;：: ")
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "evidence": evidence,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "piclist内introduce标题姓名与北京市职务文本",
            }
        )
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
