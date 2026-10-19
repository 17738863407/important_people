from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """压缩网页字段中的排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导之窗菜单顺序解析“原始职务：姓名”强结构字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, link in enumerate(soup.select("#my_menu a[href]"), start=1):
        text = clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<duty>[^：:]+)[：:]\s*(?P<name>[\u4e00-\u9fff·]{2,8})", text)
        if not match:
            continue
        name = clean_text(match.group("name")).replace(" ", "")
        duty = clean_text(match.group("duty")).strip(" ：:，,。")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, str(link.get("href") or "")),
                "source_order": str(source_order),
                "confidence": "high",
                "parser": "guizhou_defense_mobilization_menu_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2179",
    "page_type": "多人物详情合并页",
    "structure_group": "贵州国动办领导职务冒号姓名菜单",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "guizhou_defense_mobilization_menu_v2",
    "leader_region_selector": "#my_menu",
    "name_selector": "#my_menu a[href]冒号后文本",
    "duty_selector": "#my_menu a[href]冒号前文本",
    "detail_link_selector": "#my_menu a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "menu_link_only",
        "detail_collector_type": "none",
    },
    "risk_flag": "页面含大量友情链接，人物范围严格限定#my_menu领导之窗菜单；不向短职务补写机构名",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
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
