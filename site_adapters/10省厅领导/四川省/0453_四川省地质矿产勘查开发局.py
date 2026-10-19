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
    "rule_id": "0453",
    "domain": "dkj.sc.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "sichuan_geology_leader_card",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_sichuan_geology_leader_card_v2",
    "leader_region_selector": ".leaderdiv li",
    "row_link_selector": "a[href]",
    "row_text_selector": "a p",
    "detail_strategy": {
        "required": False,
        "mode": "list_item_link",
    },
    "risk_flag": "领导卡片外存在导航和单位信息；仅解析.leaderdiv li",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性清理排版空白与标点两侧空格。"""
    text = (value or "").replace("\u3000", " ").replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s*([、，,；;：:])\s*", r"\1", text)


def clean_name(value: str) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导卡片DOM顺序提取职务、姓名和独立人物页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    source_url = str(page_rule["url"]).strip()
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for item in soup.select(str(page_rule["leader_region_selector"])):
        link = item.select_one(str(page_rule["row_link_selector"]))
        parts = item.select(str(page_rule["row_text_selector"]))
        if len(parts) < 2:
            continue

        duty = clean_text(parts[0].get_text(" ", strip=True))
        name = clean_name(parts[1].get_text(" ", strip=True))
        if not duty or not re.fullmatch(r"[\u4e00-\u9fa5·]{2,8}", name):
            continue

        href = str(link.get("href") or "").strip() if link else ""
        detail_url = urljoin(final_url or source_url, href) if href else ""
        if detail_url in {source_url, final_url}:
            detail_url = ""

        key = (name, duty, detail_url)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule["parser"]),
                "selector_summary": ".leaderdiv li内首个p职务、第二个p姓名及a[href]",
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
