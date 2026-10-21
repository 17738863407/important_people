from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {"rule_id": "4303", "page_type": "linked_leader_list", "load_mode": "http", "parser": "custom", "risk": "规则入口为市政府领导直达页；兼容旧入口中的市政府领导标签。", "confidence": "high"}


def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup
    import requests

    entry = BeautifulSoup(html, "html.parser")
    soup = entry
    response_url = final_url
    if not entry.select_one("#swld-szfld .list li"):
        tab = next((a for a in entry.select("a[href]") if a.get_text(" ", strip=True) == "市政府领导"), None)
        session = requests.Session()
        if tab is None:
            entry_response = session.get(str(page_rule["url"]), headers={"User-Agent": "Mozilla/5.0"}, timeout=25, verify=False)
            entry_response.raise_for_status()
            entry_response.encoding = "utf-8"
            entry = BeautifulSoup(entry_response.text, "html.parser")
            tab = next((a for a in entry.select("a[href]") if a.get_text(" ", strip=True) == "市政府领导"), None)
            final_url = entry_response.url
            if tab is None:
                return []
        target = urljoin(final_url, tab["href"])
        response = session.get(target, headers={"User-Agent": "Mozilla/5.0"}, timeout=25, verify=False)
        response.raise_for_status()
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
        response_url = response.url
    rows: list[dict[str, str]] = []
    for item in soup.select("#swld-szfld .list li"):
        title = item.select_one("h3.title")
        link = title.select_one("a[href]") if title else None
        duty = title.select_one(".job") if title else None
        if link and duty:
            rows.append({"name": link.get_text(" ", strip=True), "duty": duty.get_text(" ", strip=True), "detail_url": urljoin(response_url, link["href"])})
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
