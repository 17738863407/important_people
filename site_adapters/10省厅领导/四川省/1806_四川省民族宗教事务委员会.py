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
    "rule_id": "1806",
    "domain": "mzw.sc.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "sichuan_ethnic_religious_dwgk_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_sichuan_ethnic_religious_dwgk_cards_v2",
    "leader_region_selector": ".dwgk_ld_1_info",
    "name_selector": ".dwgk_ld_1_info_desc_1",
    "description_selector": ".dwgk_ld_1_info_desc_2",
    "duty_start_label": "职务：",
    "duty_end_label": "分管工作：",
    "detail_strategy": {
        "required": False,
        "mode": "name_link",
    },
    "risk_flag": "人物卡片同时含长篇分管工作；只保留职务标签与分管工作标签之间的文本",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def normalize_space(value: str) -> str:
    """压缩人物卡片中的连续排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物卡片DOM顺序提取姓名、原始职务和独立人物页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    source_url = final_url or str(page_rule["url"])
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for card in soup.select(str(page_rule["leader_region_selector"])):
        name_node = card.select_one(str(page_rule["name_selector"]))
        description_node = card.select_one(str(page_rule["description_selector"]))
        if name_node is None or description_node is None:
            continue

        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        description = normalize_space(description_node.get_text(" ", strip=True))
        start_label = str(page_rule["duty_start_label"])
        end_label = str(page_rule["duty_end_label"])
        if start_label not in description:
            continue
        duty = description.split(start_label, 1)[1].split(end_label, 1)[0].strip()
        if not duty or name in seen or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue

        href = str(name_node.get("href") or "").strip()
        detail_url = urljoin(source_url, href) if href else ""
        if detail_url in {source_url, str(page_rule["url"])}:
            detail_url = ""

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule["parser"]),
                "selector_summary": "人物卡片姓名链接及职务标签与分管工作标签之间文本",
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
