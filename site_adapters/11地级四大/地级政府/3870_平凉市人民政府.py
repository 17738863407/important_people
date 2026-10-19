from __future__ import annotations
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """只解析轮播中的市政府领导页签，并继承职务标题。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser"); source = final_url or str(page_rule.get("url", "")); rows = []
    slide = next((x for x in soup.select("#leader-swiper-container .swiper-slide")
                  if x.select_one("h1") and clean_text(x.select_one("h1").get_text(" ", strip=True)) == "市政府领导"), None)
    if slide is None: return rows
    duty = ""
    container = slide.select_one(".leader-container") or slide
    for child in container.find_all(recursive=False):
        if child.name == "h2":
            duty = clean_text(child.get_text(" ", strip=True))
            continue
        for anchor in ([child] if child.name == "a" else child.select("a.leader-card--v[href]")):
            if not anchor.get("href"): continue
            name_node = anchor.select_one(".leader-name")
            name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
            if duty and re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                rows.append({"name": name, "duty": "", "evidence": duty,
                             "detail_url": urljoin(source, str(anchor.get("href") or "")),
                             "confidence": "high", "parser": "page_inline_pingliang_government_slide_v1"})
    return rows

PAGE_RULE = {"rule_id": "3870", "page_type": "多机构领导轮播", "load_mode": "静态HTML直出",
             "fetch_mode": "raw_http", "_fetch_mode_override": True, "extract_mode": "cards",
             "parser": "page_inline_pingliang_government_slide_v1",
             "leader_region_selector": "#leader-swiper-container .swiper-slide",
             "name_selector": ".leader-name", "duty_selector": "h2",
             "detail_link_selector": "a.leader-card--v[href]", "locator_strategy": "custom_parse_page",
             "risk_flag": "同页含党委、人大、政协，按市政府标题严格限定", "confidence": "high"}

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")

if __name__ == "__main__": main()
