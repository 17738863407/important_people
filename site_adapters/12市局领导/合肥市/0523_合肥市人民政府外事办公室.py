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
    """压缩网页文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """解析领导表格中“原始职务——姓名”的强结构标题。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.xxgk-table-list")
    if table is None:
        raise ValueError("未找到领导表格 table.xxgk-table-list")

    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=table.xxgk-table-list；"
        "row=tbody > tr.mc；name/duty=a.title文本按末个——分隔；detail=a.title[href]"
    )
    for row in table.select("tbody > tr.mc"):
        link = row.select_one("td.title-td > a.title[href]")
        if link is None:
            continue
        raw_text = clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
        if "——" not in raw_text:
            continue
        duty, name = [clean_text(part) for part in raw_text.rsplit("——", 1)]
        name = name.replace(" ", "")
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        detail_url = urljoin(base_url, str(link.get("href") or ""))
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": raw_text,
                "detail_url": detail_url,
                "confidence": "high",
                "parser": "page_inline_hefei_public_duty_name_table_v1",
                "selector_summary": selector_summary,
            }
        )

    if not rows:
        raise ValueError("领导表格未解析出有效“职务——姓名”记录")
    return rows


PAGE_RULE = {
    "rule_id": "0523",
    "page_type": "人物表格页",
    "structure_group": "hefei_public_duty_name_table",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "table_direct",
    "collector": "browser_dom",
    "parser": "page_inline_hefei_public_duty_name_table_v1",
    "leader_region_selector": "table.xxgk-table-list",
    "name_selector": "td.title-td > a.title",
    "duty_selector": "td.title-td > a.title",
    "detail_link_selector": "td.title-td > a.title[href]",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "普通HTTP连续返回521；已核验general环境Playwright可稳定取得唯一可见领导表格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "table.xxgk-table-list",
            "name_selector": "td.title-td > a.title",
            "duty_selector": "td.title-td > a.title",
            "detail_link_selector": "td.title-td > a.title[href]",
        },
        "api": {
            "enabled": False,
            "reason": "当前公开页面的可见领导表格直接提供职务、姓名和人物详情链接",
        },
        "migration": {
            "source": "failed_script_v3_task7",
            "verified_status": "online_verified_20260808",
            "behavior_changed": True,
        },
    },
}


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
