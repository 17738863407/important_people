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
    "rule_id": "0156",
    "page_type": "人事事项正文名单",
    "structure_group": "正文职务标签分组名单",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "ChangchunCppccPersonnelTextParser_v2",
    "leader_region_selector": "div.TRS_Editor",
    "risk_flag": "正文名单含日期、性别与民族括注，且无人物详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(text: str) -> str:
    """归一正文排版空白。"""
    return " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())


def _clean_name(text: str) -> str:
    """去除名单中的性别、民族括注及姓名排版空白。"""
    return "".join(re.sub(r"（[^）]*）", "", _clean_text(text)).split())


def _extract_group_names(text: str) -> list[str]:
    """从已限定的常务委员名单片段按原始阅读顺序提取姓名。"""
    pattern = r"(?:[\u4e00-\u9fff]{2,3}|[\u4e00-\u9fff]\s+[\u4e00-\u9fff])(?:（[^）]+）)?"
    return [name for raw in re.findall(pattern, text) if (name := _clean_name(raw))]


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """仅解析政协人事事项正文中的三个明确职务分组。"""
    soup = BeautifulSoup(html, "html.parser")
    editor = soup.select_one(rule["leader_region_selector"])
    if editor is None:
        return []
    text = _clean_text(editor.get_text(" ", strip=True))
    records: list[dict] = []

    labeled_pattern = r"(副主席|秘书长)：\s*([\u4e00-\u9fff](?:\s*[\u4e00-\u9fff]){1,3}?)(?=\s+(?:副主席|秘书长|常务委员)|$)"
    for duty, raw_name in re.findall(labeled_pattern, text):
        name = _clean_name(raw_name)
        if name:
            records.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "parser": rule["parser"],
                    "selector_summary": "TRS_Editor正文中的副主席/秘书长标签",
                }
            )

    member_match = re.search(r"(常务委员（[^）]*）)[:：]\s*(.+)$", text)
    if member_match:
        for name in _extract_group_names(member_match.group(2)):
            records.append(
                {
                    "name": name,
                    "duty": "常务委员",
                    "evidence": "常务委员",
                    "detail_url": "",
                    "parser": rule["parser"],
                    "selector_summary": "TRS_Editor正文中的常务委员分组名单",
                }
            )
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
