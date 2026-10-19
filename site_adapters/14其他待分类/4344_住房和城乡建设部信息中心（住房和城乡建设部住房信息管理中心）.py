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
    "rule_id": "4344",
    "page_type": "中心领导职务姓名段落页",
    "structure_group": "mohurdic_leader_paragraphs_v1",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_mohurdic_leaders_v1",
    "leader_region_selector": "p:has(strong)",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "职务标签存在排版空格，按同段strong标签与姓名文本解析。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "strong_label_paragraph",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """提取中心领导段落中的职务标签和姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for paragraph in soup.select("p"):
        label = paragraph.find("strong")
        if label is None:
            continue
        duty = re.sub(r"\s+", "", label.get_text(" ", strip=True)).rstrip("：:")
        if duty not in {"党委书记", "副书记、主任", "副主任", "纪委书记"}:
            continue
        full_text = re.sub(r"\s+", "", paragraph.get_text(" ", strip=True))
        name = full_text.removeprefix(duty + "：").removeprefix(duty + ":")
        if re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
            rows.append({"name": name, "duty": duty, "detail_url": ""})
    if not rows:
        raise RuntimeError("中心领导页未解析到职务标签与姓名段落")
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
