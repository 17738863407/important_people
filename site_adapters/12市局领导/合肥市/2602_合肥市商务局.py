from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2602",
    "page_type": "人物表格页",
    "load_mode": "动态DOM渲染",
    "browser_render_wait_ms": 8000,
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "leader_region_selector": "table.xxgk-table-list",
    "person_selector": "a.title[href]",
    "risk_flag": "页面包含大量导航，必须限制在机构领导结果表",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按机构领导结果表顺序解析“职务：姓名”标题。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if not region:
        raise RuntimeError("未找到机构领导结果表 table.xxgk-table-list")
    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    for link in region.select(page_rule["person_selector"]):
        title = clean_text(link.get_text(" ", strip=True))
        if "：" not in title:
            continue
        duty, name = (clean_text(part) for part in title.rsplit("：", 1))
        if not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name):
            continue
        href = clean_text(link.get("href"))
        rows.append({
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": urljoin(base_url, href) if href else "",
            "confidence": "high",
            "parser": "page_inline_hefei_commerce_title_v1",
            "selector_summary": "region=table.xxgk-table-list；person=a.title[href]；pattern=职务：姓名",
        })
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
