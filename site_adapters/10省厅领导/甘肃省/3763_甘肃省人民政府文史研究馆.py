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


PAGE_RULE = {
    "rule_id": "3763", "page_type": "信息公开首页领导简介列表", "structure_group": "gswsg_leader_intro_list_v1",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_to_detail", "collector": "static_http",
    "parser": "page_inline_gswsg_leader_intro_list_v1", "leader_region_selector": ".list_li", "name_selector": "li a",
    "duty_selector": "li a", "detail_link_selector": "li a[href]", "detail_strategy": {"required": False, "mode": "list_link"},
    "confidence": "high", "filter_policy": "strong_no_wordlist", "risk_flag": "必须先按列表标题锁定领导简介区，排除历任馆长、年报和机关处室；详情链接须来自当前人物列表项",
    "locator_strategy": "titled_list_block_anchor_text_and_href",
}


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    block = next((node for node in soup.select(".list_li") if clean_text((node.select_one(".list_menu") or node).get_text(" ", strip=True)).startswith("领导简介")), None)
    if block is None:
        return []
    rows: list[dict[str, str]] = []
    for link in block.select("ul li a[href]"):
        text = clean_text(link.get_text(" ", strip=True))
        parts = text.rsplit(" ", 1)
        if len(parts) != 2:
            continue
        duty, name = parts[0].replace("、", "；"), parts[1].replace(" ", "")
        detail_url = urljoin(final_url, link.get("href", ""))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) and duty:
            rows.append({"name": name, "duty": duty, "detail_url": detail_url, "source_text": duty, "method": page_rule["parser"], "note": "scope=leader_intro_list；order=list_item_order；detail=list_item_href"})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
