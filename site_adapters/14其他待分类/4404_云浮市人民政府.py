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
    "rule_id": "4404",
    "page_type": "government_leader_detail_directory",
    "load_mode": "http",
    "fetch_mode": "raw_http",
    "parser": "custom",
    "risk": "侧栏只给出职务分组；按侧栏顺序逐页读取人物卡片中的完整现任职务。",
    "confidence": "high",
}


def _request_text(url: str) -> str:
    import requests

    session = requests.Session()
    session.trust_env = False
    response = session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """遍历领导之窗侧栏，并从各详情页人物卡片提取完整职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    directory = soup.select_one(".ldzc-left")
    if directory is None:
        return []
    rows: list[dict[str, str]] = []
    for link in directory.select("ul.ldzc-menu2 li a[href]"):
        detail_url = link["href"]
        detail = BeautifulSoup(_request_text(detail_url), "html.parser")
        name_node = detail.select_one(".ldzc-right .ldr h1")
        duty_node = detail.select_one(".ldzc-right .ldr > .job")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True)) if name_node else ""
        duty = duty_node.get_text(" ", strip=True) if duty_node else ""
        if name and duty:
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
