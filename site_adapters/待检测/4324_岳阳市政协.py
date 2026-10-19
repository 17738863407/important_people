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
    "rule_id": "4324",
    "page_type": "leader_cards",
    "load_mode": "http",
    "parser": "custom",
    "risk": "主席成员卡片提供真实人物详情页；部分卡片摘要未写职务，须以本次详情页现职句核验。",
    "confidence": "high",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    """按“主席成员”卡片顺序提取，并从当前详情页取得现职句。"""
    from bs4 import BeautifulSoup
    import requests

    soup = BeautifulSoup(html, "html.parser")
    group = soup.select_one("#zxcy")
    if group is None:
        return []
    session = requests.Session()
    session.trust_env = False
    headers = {"User-Agent": "Mozilla/5.0"}
    rows: list[dict[str, str]] = []
    for card in group.select(".box_bd li"):
        name_node = card.select_one(".text > span")
        link = card.select_one("a[href][title]") or card.select_one(".img a[href]")
        if name_node is None or link is None:
            continue
        name = re.sub(r"[\s\u3000]+", "", name_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        detail_url = urljoin(final_url, link["href"])
        detail = session.get(detail_url, headers=headers, timeout=30)
        detail.raise_for_status()
        detail_text = BeautifulSoup(detail.content, "html.parser").get_text(" ", strip=True)
        duty_match = re.search(
            r"现任\s*(.*?)(?:[。！？]|人物履历|工作简历|\d{4}[.．]\d{2}|$)",
            detail_text,
        )
        duty = duty_match.group(1).strip() if duty_match else ""
        if not duty:
            summary = card.select_one(".introduced")
            summary_text = summary.get_text(" ", strip=True) if summary else ""
            summary_match = re.search(r"现任\s*([^。！？]+)", summary_text)
            duty = summary_match.group(1).strip() if summary_match else ""
        if duty:
            duty = re.sub(r"\s+", "", duty)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url})
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
