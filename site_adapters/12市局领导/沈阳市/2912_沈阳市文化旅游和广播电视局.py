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
    "rule_id": "2912", "page_type": "人物列表完整页", "structure_group": "shenyang_culture_labeled_paragraphs_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_culture_labeled_paragraphs_v2",
    "leader_region_selector": ".view", "name_selector": "姓名标签p",
    "duty_selector": "随后职务标签p", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "工作分工段不得混入原始职务；多人共用文章不得作为个人详情页",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def field_value(text: str, label: str) -> str:
    """解析当前正文的“标签：值”段落。"""
    match = re.fullmatch(rf"{label}\s*[:：]\s*(.+)", text)
    return clean_text(match.group(1)) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文顺序解析连续的姓名、职务、工作分工三段。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    views = soup.select(".view")
    if len(views) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(views)}")
    paragraphs = [clean_text(node.get_text(" ", strip=True)) for node in views[0].select("p")]
    paragraphs = [value for value in paragraphs if value]
    records: list[object] = []
    seen_names: set[str] = set()
    index = 0
    while index < len(paragraphs):
        name_value = field_value(paragraphs[index], "姓名")
        if not name_value:
            index += 1
            continue
        if index + 2 >= len(paragraphs):
            raise RuntimeError("人物字段组不完整")
        evidence = field_value(paragraphs[index + 1], "职务")
        work = field_value(paragraphs[index + 2], "工作分工")
        name = re.sub(r"\s+", "", name_value)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or not work:
            raise RuntimeError(f"人物姓名、职务或工作分工字段异常：{name}")
        if name in seen_names:
            raise RuntimeError(f"人物姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
        index += 3
    if not records:
        raise RuntimeError("领导正文没有有效人物字段组")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
