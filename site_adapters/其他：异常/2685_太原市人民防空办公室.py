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
    "rule_id": "2685",
    "page_type": "人物列表完整页",
    "structure_group": "taiyuan_article_explicit_duty_name",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "leader_region_selector": "div#Zoom",
    "risk_flag": "当前在线响应缺少文章正文；不得从标题、导航或历史页面推断人物",
    "confidence": "low",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """仅接受文章正文中明确的“职务：姓名”独立文本行。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("div#Zoom")
    if region is None:
        raise RuntimeError("当前在线响应缺少文章正文div#Zoom，无法核验姓名与职务")
    rows: list[dict[str, str]] = []
    for node in region.select("p, strong"):
        compact = re.sub(r"\s+", "", node.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<duty>[^：:]{2,40})[：:](?P<name>[一-鿿·]{2,4})", compact)
        if match is None:
            continue
        duty = match.group("duty")
        rows.append(
            {
                "order": str(len(rows) + 1),
                "name": match.group("name"),
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": str(page_rule.get("confidence") or "low"),
                "parser": "inline_taiyuan_article_explicit_duty_name_v1",
            }
        )
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
