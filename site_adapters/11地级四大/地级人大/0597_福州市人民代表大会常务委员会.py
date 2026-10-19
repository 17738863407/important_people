from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    """压缩页面字段中的排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def split_group_names(raw_text: str) -> list[str]:
    """按页面不换行空格分组，并合并被拆开的二字姓名。"""
    import re

    text = re.sub(r"[（(][^）)]*[）)]", "", raw_text)
    if "\xa0" not in text:
        name = re.sub(r"\s+", "", text)
        return [name] if re.fullmatch(r"[一-鿿·]{2,6}", name) else []

    parts = [re.sub(r"\s+", "", part) for part in re.split(r"\xa0+", text)]
    parts = [part for part in parts if part]
    names: list[str] = []
    index = 0
    while index < len(parts):
        current = parts[index]
        if (
            len(current) == 1
            and index + 1 < len(parts)
            and len(parts[index + 1]) == 1
        ):
            current += parts[index + 1]
            index += 1
        if re.fullmatch(r"[一-鿿·]{2,6}", current):
            names.append(current)
        index += 1
    return names


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析组成人员页面中的主任、副主任和秘书长领导分组。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    del final_url
    rows: list[dict[str, str]] = []
    accepted_roles = {"主任", "副主任", "秘书长"}
    for paragraph in soup.select("p[align='justify']"):
        role_node = paragraph.select_one("b")
        if role_node is None:
            continue
        role_text = re.sub(r"[（(].*$", "", role_node.get_text("", strip=True))
        role = re.sub(r"[\s\u3000]+", "", role_text).strip("：:")
        if role not in accepted_roles:
            continue
        raw_names = "".join(str(node) for node in role_node.next_siblings)
        raw_names = BeautifulSoup(raw_names, "html.parser").get_text(" ")
        names = split_group_names(raw_names)
        for name in names:
            rows.append(
                {
                    "order": str(len(rows) + 1),
                    "name": name,
                    "duty": role,
                    "detail_url": "",
                    "evidence": role,
                    "confidence": "high",
                    "parser": "page_inline_fzrd_role_group_v2",
                }
            )
    return rows


PAGE_RULE = {
    "rule_id": "0597",
    "page_type": "职务分组名单页",
    "structure_group": "fzrd_committee_role_groups",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "role_group",
    "collector": "raw_http",
    "parser": "page_inline_fzrd_role_group_v2",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "末尾委员名单嵌在标题段落后的表格中，按精确分组标题排除；主任、副主任、秘书长姓名含字距空格，需保持页面原序",
    "confidence": "high",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
