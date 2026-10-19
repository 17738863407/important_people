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
    "rule_id": "4168",
    "page_type": "文联理事会领导名单页",
    "structure_group": "cas_federation_officer_groups",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "parser": "page_inline_cas_federation_officers_v1",
    "leader_region_selector": ".TRS_Editor",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同页后部含大规模理事名单；仅提取主席、名誉主席、副主席、秘书长、副秘书长和顾问分组。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """删除名单中的排版空白并统一半角括号。"""
    return re.sub(r"\s+", "", value or "").replace("(", "（").replace(")", "）")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按官网分组顺序解析第六届文联理事会领导成员。"""
    from bs4 import BeautifulSoup, Tag

    editor = BeautifulSoup(html, "html.parser").select_one(".TRS_Editor")
    if not isinstance(editor, Tag):
        raise RuntimeError("未定位到第六届文联理事会正文")

    order: list[str] = []
    duties: dict[str, list[str]] = {}

    def add(name: str, duty: str) -> None:
        normalized_name = re.sub(r"\s+", "", name)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", normalized_name):
            return
        if normalized_name not in duties:
            order.append(normalized_name)
            duties[normalized_name] = []
        if duty and duty not in duties[normalized_name]:
            duties[normalized_name].append(duty)

    paragraphs = editor.find_all("p")
    chairman_node = paragraphs[0] if paragraphs else None
    chairman_value = ""
    if isinstance(chairman_node, Tag):
        direct_fonts = chairman_node.find_all("font", recursive=False)
        if direct_fonts:
            chairman_value = direct_fonts[-1].get_text(" ", strip=True)
    chairman_parts = re.split(r"\s{2,}", chairman_value.strip(), maxsplit=1)
    if len(chairman_parts) == 2:
        add(clean_text(chairman_parts[0]), f"主席；{clean_text(chairman_parts[1])}")

    honorary_text = clean_text(paragraphs[1].get_text(" ", strip=True)) if len(paragraphs) > 1 else ""
    honorary_match = re.fullmatch(r"名誉主席[：:]([\u4e00-\u9fff·]{2,8})", honorary_text)
    if honorary_match:
        add(honorary_match.group(1), "名誉主席")

    tables = editor.find_all("table")
    if len(tables) < 2:
        raise RuntimeError("副主席或顾问名单表格缺失")
    for cell in tables[0].select("td"):
        add(clean_text(cell.get_text(" ", strip=True)), "副主席")

    role_labels = {"秘书长", "副秘书长"}
    for heading in editor.find_all(["b", "strong"]):
        role = clean_text(heading.get_text(" ", strip=True)).rstrip("：:")
        if role not in role_labels:
            continue
        value_node = next(
            (node for node in heading.find_all_next("p") if node.get_text(" ", strip=True)),
            None,
        )
        if not isinstance(value_node, Tag):
            continue
        raw_names = value_node.get_text(" ", strip=True)
        for name in re.findall(r"[\u4e00-\u9fff·]{2,8}", raw_names):
            add(name, role)

    for cell in tables[1].select("td"):
        add(clean_text(cell.get_text(" ", strip=True)), "顾问")

    if not order:
        raise RuntimeError("第六届文联理事会领导分组未抽取到人物")
    return [
        {
            "name": name,
            "duty": "；".join(duties[name]),
            "evidence": "；".join(duties[name]),
            "detail_url": "",
            "confidence": "high",
            "parser": page_rule["parser"],
            "selector_summary": "scope=.TRS_Editor；include=主席至顾问；exclude=理事名单",
        }
        for name in order
    ]


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
