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
    return " ".join(str(value or "").replace("\u200b", "").replace("\u3000", " ").replace("\xa0", " ").split())

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从每个人物卡片简介中提取当前现任句。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser"); source = final_url or str(page_rule.get("url", "")); rows = []
    for card in soup.select(".fileName li"):
        anchor, intro = card.select_one("h4 a[href]"), card.select_one("p[class^='fileDetails']")
        name = clean_text(anchor.get_text(" ", strip=True) if anchor else "").replace(" ", "")
        text = clean_text(intro.get_text(" ", strip=True) if intro else "")
        match = re.search(r"现任([^。]+)", text)
        evidence = clean_text(match.group(1)).rstrip("。；; ") if match else ""
        if anchor and evidence and re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            rows.append({"name": name, "duty": "", "evidence": evidence,
                         "detail_url": urljoin(source, str(anchor.get("href") or "")),
                         "confidence": "high", "parser": "page_inline_puer_current_sentence_cards_v1"})
    return rows

PAGE_RULE = {"rule_id": "3871", "page_type": "领导简介卡片", "load_mode": "静态HTML直出",
             "fetch_mode": "raw_http", "_fetch_mode_override": True, "extract_mode": "cards",
             "parser": "page_inline_puer_current_sentence_cards_v1", "leader_region_selector": ".fileName",
             "name_selector": ".fileName li h4 a", "duty_selector": ".fileName li .fileDetails",
             "detail_link_selector": ".fileName li h4 a[href]", "locator_strategy": "custom_parse_page",
             "risk_flag": "简介含履历，只提取人物卡片内现任句", "confidence": "high"}

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")

if __name__ == "__main__": main()
