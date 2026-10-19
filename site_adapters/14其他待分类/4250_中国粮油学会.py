from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4250",
    "page_type": "领导分组名单",
    "structure_group": "中国粮油学会领导成员分组列表",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_ccoa_members_v1",
    "leader_region_selector": ".center.width_ej.shadow",
    "name_selector": "ul.ul_qj > li > a",
    "duty_selector": ".qj_title 与列表内职务文本",
    "detail_link_selector": "ul.ul_qj > li > a[href]",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "同一人可在理事会与秘书处重复出现，需保留并合并页面明确的多项职务。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析分组标题和列表内显式职务，保持官网列表顺序。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    role_pattern = re.compile(r"(副?理事长|副?监事长|监事|秘书长|副秘书长)")
    name_pattern = re.compile(r"[\u4e00-\u9fff·]{2,8}")
    rows_by_name: dict[str, dict[str, str]] = {}
    order: list[str] = []
    base_url = final_url or str(page_rule["url"])

    for heading in soup.select(".center.width_ej.shadow > .qj_title"):
        group_title = re.sub(r"\s+", "", heading.get_text(" ", strip=True))
        listing = heading.find_next_sibling("ul", class_="ul_qj")
        if not listing:
            continue
        current_role = group_title if group_title == "首席科学家" else ""
        for link in listing.select("li > a"):
            text = re.sub(r"\s+", "", link.get_text(" ", strip=True))
            role_match = role_pattern.search(text)
            if role_match:
                current_role = role_match.group(1)
                name = text.replace(current_role, "")
            else:
                name = text
            if not current_role or not name_pattern.fullmatch(name):
                continue
            detail_url = urljoin(base_url, link.get("href", "")) if link.get("href", "").strip() else ""
            if name not in rows_by_name:
                rows_by_name[name] = {
                    "name": name,
                    "duty": current_role,
                    "evidence": current_role,
                    "detail_url": detail_url,
                    "parser": page_rule["parser"],
                    "selector_summary": "qj_title分组 + ul.ul_qj领导名单",
                }
                order.append(name)
                continue
            row = rows_by_name[name]
            duties = row["duty"].split("；")
            if current_role not in duties:
                row["duty"] = f"{row['duty']}；{current_role}"
                row["evidence"] = row["duty"]
            if detail_url and not row["detail_url"]:
                row["detail_url"] = detail_url
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
