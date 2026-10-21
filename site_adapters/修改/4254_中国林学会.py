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
    "rule_id": "4254",
    "page_type": "理事会领导名单正文",
    "structure_group": "中国林学会第十二届理事会领导职务段落",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_csf_council_leaders_v1",
    "leader_region_selector": ".nameList",
    "name_selector": "p",
    "duty_selector": "理事长、副理事长、秘书长、副秘书长标题段落",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文还列有常务理事和理事，且秘书长段包含已结束任期人员，必须排除。",
    "confidence": "medium",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """依照领导职务标题读取人员，排除理事名单与已结束的秘书长任期。"""
    from bs4 import BeautifulSoup

    def split_names(value: str) -> list[str]:
        pieces = [piece for piece in re.split(r"\s+", value.strip()) if piece]
        names: list[str] = []
        index = 0
        while index < len(pieces):
            piece = pieces[index]
            if len(piece) == 1 and index + 1 < len(pieces) and len(pieces[index + 1]) == 1:
                names.append(piece + pieces[index + 1])
                index += 2
            elif re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", piece):
                names.append(piece)
                index += 1
            else:
                index += 1
        return names

    soup = BeautifulSoup(html, "html.parser")
    active_role = ""
    allowed_roles = {"理事长", "副理事长", "秘书长", "副秘书长"}
    rows_by_name: dict[str, dict[str, str]] = {}
    order: list[str] = []
    for paragraph in soup.select(".nameList p"):
        text = re.sub(r"\s+", " ", paragraph.get_text(" ", strip=True)).strip()
        if not text:
            continue
        heading = re.fullmatch(r"(理事长|副理事长|秘书长|副秘书长)(?:\(共\d+名\))?", text)
        if heading:
            active_role = heading.group(1)
            continue
        if re.fullmatch(r"(常务理事|理事)(?:\(共\d+名\))?", text):
            active_role = ""
            continue
        if active_role not in allowed_roles:
            continue
        if active_role == "秘书长":
            current = re.fullmatch(r"([\u4e00-\u9fff·]{2,8})（\d{4}\.\d+-）.*", text)
            if not current:
                continue
            names = [current.group(1)]
        else:
            names = split_names(text)
        for name in names:
            if name not in rows_by_name:
                rows_by_name[name] = {
                    "name": name,
                    "duty": active_role,
                    "evidence": active_role,
                    "parser": page_rule["parser"],
                    "selector_summary": ".nameList领导职务标题与其后人员段落",
                }
                order.append(name)
                continue
            previous = rows_by_name[name]
            if active_role not in previous["duty"].split("；"):
                previous["duty"] = f"{previous['duty']}；{active_role}"
                previous["evidence"] = previous["duty"]
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
