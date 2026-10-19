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
    "rule_id": "4262",
    "page_type": "理事会领导正文名单",
    "structure_group": "中国民族医药学会第四届理事会领导名单",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_cmam_leaders_v1",
    "leader_region_selector": ".list-h .wrap-body",
    "name_selector": "p",
    "duty_selector": "职务标题与其后姓名段落",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "副会长、秘书长、副秘书长均以标题分组，副秘书长的多人名单在同一复杂嵌套段落。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按当前职务标题解析单人或多人姓名段落，并合并同一人的明确职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    active_role = ""
    allowed_roles = {"会长", "副会长", "副会长兼秘书长", "副秘书长"}
    rows_by_name: dict[str, dict[str, str]] = {}
    order: list[str] = []
    for paragraph in soup.select(".list-h .wrap-body > p"):
        text = re.sub(r"\s+", " ", paragraph.get_text(" ", strip=True)).strip()
        if not text:
            continue
        heading = re.fullmatch(r"(会长|副会长|副会长兼秘书长|副秘书长)(?:（[^）]+）)?", text)
        if heading:
            active_role = heading.group(1)
            continue
        if active_role not in allowed_roles:
            continue
        names = [piece for piece in text.split(" ") if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", piece)]
        for name in names:
            if name not in rows_by_name:
                rows_by_name[name] = {
                    "name": name,
                    "duty": active_role,
                    "evidence": active_role,
                    "parser": page_rule["parser"],
                    "selector_summary": ".list-h理事会职务标题与姓名段落",
                }
                order.append(name)
                continue
            row = rows_by_name[name]
            if active_role == "副会长兼秘书长" and row["duty"] == "副会长":
                row["duty"] = active_role
                row["evidence"] = active_role
                continue
            if active_role not in row["duty"].split("；"):
                row["duty"] = f"{row['duty']}；{active_role}"
                row["evidence"] = row["duty"]
    return [rows_by_name[name] for name in order]


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
