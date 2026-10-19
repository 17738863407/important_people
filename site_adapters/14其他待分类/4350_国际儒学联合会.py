from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4350",
    "page_type": "现任领导分组页",
    "structure_group": "ica_visible_leader_groups_v1",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_ica_visible_leaders_v1",
    "leader_region_selector": ".Leader_Item.Show",
    "name_selector": ".Leader_Item_Leng h4",
    "duty_selector": ".Leader_Item_Title",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面同时保留display:none的荣誉领导折叠项并重复移动端结构；仅抽取可见当前领导并去重。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "visible_group_rows",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """提取可见的会长、理事长和常务副会长分组。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for line in soup.select(".Leader_Item.Show .Leader_Item_Line"):
        style = str(line.get("style") or "").replace(" ", "").lower()
        if "display:none" in style:
            continue
        duty_node = line.select_one(".Leader_Item_Title")
        duty = " ".join(duty_node.get_text(" ", strip=True).split()) if duty_node else ""
        for name_node in line.select(".Leader_Item_Leng h4"):
            name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
            key = (name, duty)
            if duty and re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) and key not in seen:
                seen.add(key)
                rows.append({"name": name, "duty": duty, "detail_url": ""})
    if not rows:
        raise RuntimeError("现任领导区未解析到可见领导分组")
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
