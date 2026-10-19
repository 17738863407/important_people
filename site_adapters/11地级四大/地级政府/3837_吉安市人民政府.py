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
    return " ".join(str(value or "").replace("\u3000", " ").split())

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """仅在市政府领导板块内按职务分组提取。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    section = next((node for node in soup.select("div.ldzc_slide") if node.select_one(".ldzc_slide_top") and node.select_one(".ldzc_slide_top").get_text(" ", strip=True) == "市政府领导"), None)
    groups = section.select("div.szfld") if section else []
    source_url = final_url or str(page_rule.get("url", ""))
    rows = []
    for group in groups:
        duty_node = group.select_one(":scope > span")
        duty = clean_text(duty_node.get_text(" ", strip=True)).replace(" ", "") if duty_node else ""
        for link in group.select("ul li a[href]"):
            node = link.select_one("p")
            name = clean_text(node.get_text(" ", strip=True)).replace(" ", "") if node else ""
            if duty and re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                rows.append({"name": name, "duty": "", "evidence": duty, "detail_url": urljoin(source_url, str(link.get("href") or "")), "confidence": "high", "parser": "page_inline_jian_government_groups_v1"})
    return rows

PAGE_RULE = {"rule_id":"3837","page_type":"同页多机构职务分组卡片页","load_mode":"静态HTML直出","fetch_mode":"raw_http","_fetch_mode_override":True,"extract_mode":"list_direct","parser":"page_inline_jian_government_groups_v1","leader_region_selector":".szfld","name_selector":"li p","duty_selector":".szfld > span","detail_link_selector":"li a[href]","locator_strategy":"custom_parse_page","risk_flag":"同页含市委领导，已以市政府标题限定","confidence":"high"}

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")

if __name__ == "__main__":
    main()
