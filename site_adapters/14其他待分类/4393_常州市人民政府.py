from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4393",
    "page_type": "government_leader_list",
    "load_mode": "http",
    "fetch_mode": "raw_http",
    "parser": "custom",
    "risk": "仅抽取市长之窗左侧市政府领导列表，排除当前人物简历、分工与活动。",
    "confidence": "high",
}


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """逐列表项提取姓名、网页职务与真实人物页链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select(".ldzc_left .ldzc_btn li"):
        link = item.select_one("a[href]")
        name_node = item.select_one("h4")
        duty_node = item.select_one("span")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True)) if name_node else ""
        duty = duty_node.get_text(" ", strip=True) if duty_node else ""
        if link and name and duty:
            detail_url = urljoin(final_url, link["href"])
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": "" if detail_url == final_url else detail_url,
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
