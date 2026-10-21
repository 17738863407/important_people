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
    "rule_id": "4288", "page_type": "市委领导分组卡片", "structure_group": "平凉市委领导可见卡片容器", "load_mode": "静态HTML直出", "extract_mode": "list_direct", "parser": "page_inline_pingliang_party_leaders_v1", "leader_region_selector": "#leader-swiper-container .leader-container", "name_selector": "市委领导容器 .leader-name", "duty_selector": "市委领导容器相邻 h2 分组标题", "detail_link_selector": "市委领导容器 a.leader-card--v[href]", "detail_strategy": {"required": True, "mode": "list_link"}, "risk_flag": "同页还含人大、政府、政协容器，且存在 display:none 历史/隐藏卡片，必须仅取市委领导首容器的可见卡片。", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按市委领导容器的分组标题和可见卡片顺序提取人员。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    container = next((box for box in soup.select("#leader-swiper-container .leader-container") if box.select_one("h1") and box.select_one("h1").get_text(strip=True) == "市委领导"), None)
    if not container:
        return []
    rows: list[dict[str, str]] = []
    rows_by_name: dict[str, dict[str, str]] = {}
    base_url = final_url or str(page_rule["url"])
    current_duty = ""
    for node in container.find_all(["h2", "a"], recursive=True):
        if node.name == "h2":
            current_duty = re.sub(r"\s+", "", node.get_text(" ", strip=True))
            continue
        if "leader-card--v" not in (node.get("class") or []) or "display:none" in (node.get("style") or "").replace(" ", ""):
            continue
        name_node = node.select_one(".leader-name")
        if not name_node or not current_duty:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        duty = "市委" + current_duty
        if name in rows_by_name:
            row = rows_by_name[name]
            if duty not in row["evidence"].split("；"):
                row["duty"] += "；" + duty
                row["evidence"] += "；" + duty
            continue
        row = {"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, node["href"]), "parser": page_rule["parser"], "selector_summary": "市委领导分组可见卡片"}
        rows_by_name[name] = row
        rows.append(row)
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
