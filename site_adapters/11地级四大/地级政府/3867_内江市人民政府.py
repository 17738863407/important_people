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
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").replace("\u2002", " ").split())

def add_group(rows: list[dict[str, str]], group: object, duty: str, source: str) -> None:
    for anchor in group.select(".zfld-zp-list a[href]"):
        name = clean_text(anchor.get_text(" ", strip=True)).replace(" ", "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            rows.append({"name": name, "duty": "", "evidence": duty,
                         "detail_url": urljoin(source, str(anchor.get("href") or "")),
                         "confidence": "high", "parser": "page_inline_neijiang_rendered_groups_v1"})

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析浏览器渲染后的市长简介及副市长、秘书长分组。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser"); source = final_url or str(page_rule.get("url", "")); rows = []
    mayor = soup.select_one(".zfld-sz-box .sz-info")
    if mayor:
        anchor, duty_node = mayor.select_one(".name a[href]"), mayor.select_one(".zw")
        name = clean_text(anchor.get_text(" ", strip=True) if anchor else "").replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        duty = re.sub(r"^现任", "", duty).rstrip("。；; ")
        if anchor and duty and re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            rows.append({"name": name, "duty": "", "evidence": duty,
                         "detail_url": urljoin(source, str(anchor.get("href") or "")),
                         "confidence": "high", "parser": "page_inline_neijiang_rendered_groups_v1"})
    for group in soup.select(".zfld-ldzp-list-box"):
        title = clean_text((group.select_one(".zfld-box-l") or group).get_text(" ", strip=True))
        duty = "秘书长" if "秘书长" in title else "副市长" if "副市长" in title else ""
        if duty: add_group(rows, group, duty, source)
    return rows

PAGE_RULE = {"rule_id": "3867", "page_type": "浏览器渲染领导分组", "load_mode": "Playwright渲染",
             "fetch_mode": "playwright", "_fetch_mode_override": True, "extract_mode": "cards",
             "parser": "page_inline_neijiang_rendered_groups_v1", "leader_region_selector": ".zfld-jj-box",
             "name_selector": ".name", "detail_link_selector": "a[href]",
             "locator_strategy": "custom_parse_page", "risk_flag": "HTTP返回403，需浏览器渲染", "confidence": "high"}

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")

if __name__ == "__main__": main()
