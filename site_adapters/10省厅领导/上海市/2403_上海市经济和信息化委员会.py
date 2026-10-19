from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2403",
    "page_type": "人物表格页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".ld-cont",
    "item_selector": ".ld-cont .ld",
    "name_selector": "[title]",
    "duty_selector": "p",
    "risk_note": "当前页面实际为人物卡片，详情地址位于卡片onclick跳转语句。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩字段排版空白，保留职务标点。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按人物卡片顺序提取独立姓名、职务和onclick详情地址。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for item in soup.select(page_rule["item_selector"]):
        duty_node = item.select_one(page_rule["duty_selector"])
        name = clean_text(item.get("title", "")).replace(" ", "")
        evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        evidence = re.sub(r"(?:（挂职）|\(挂职\)|[<＜]挂职[>＞])", "", evidence).strip(" ，、；")
        detail_match = re.search(
            r"(?:window\.)?location\.href\s*=\s*['\"]([^'\"]+)['\"]",
            item.get("onclick", ""),
        )
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence or not detail_match:
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": evidence,
                "detail_url": urljoin(final_url, detail_match.group(1)),
            }
        )

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
