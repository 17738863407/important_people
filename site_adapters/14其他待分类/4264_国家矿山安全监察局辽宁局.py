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
    "rule_id": "4264",
    "page_type": "领导信息详情列表",
    "structure_group": "国家矿山安全监察局辽宁局领导信息链接列表",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_chinamine_liaoning_leaders_v1",
    "leader_region_selector": ".list_rul",
    "name_selector": "a.dong_wor",
    "duty_selector": "链接文本中姓名后的职务",
    "detail_link_selector": "a.dong_wor[href]",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "列表同时显示发布日期，职务与姓名在同一详情链接文本中。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """通过当前领导详情列表的姓名—职务链接解析记录。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    base_url = final_url or str(page_rule["url"])
    for link in soup.select(".list_rul a.dong_wor[href]"):
        parts = [part for part in re.split(r"\s+", link.get_text(" ", strip=True)) if part]
        if len(parts) < 2:
            continue
        name, duty = parts[0], "；".join(parts[1:])
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(base_url, link["href"]),
                "parser": page_rule["parser"],
                "selector_summary": ".list_rul领导详情链接文本",
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
