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
    "rule_id": "4248",
    "page_type": "负责人列表",
    "structure_group": "新疆气象局机构与职能负责人链接列表",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_xj_cma_leader_v1",
    "leader_region_selector": "ul.mesgopen2",
    "name_selector": "li > a[href]",
    "duty_selector": "链接文本冒号前职务",
    "detail_link_selector": "li > a[href]",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "同页还列出内设机构和直属单位，必须只取负责人基本信息列表。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析“负责人基本信息”中的职务—姓名链接，保留页面原始顺序。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    base_url = final_url or str(page_rule["url"])
    for link in soup.select("ul.mesgopen2 > li > a[href]"):
        text = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        matched = re.fullmatch(r"(.+?)：([\u4e00-\u9fff·]{2,8})", text)
        if not matched:
            continue
        duty, name = matched.groups()
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(base_url, link["href"]),
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": "ul.mesgopen2负责人链接文本（职务：姓名）",
            }
        )
    return rows


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
