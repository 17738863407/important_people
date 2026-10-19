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
    """按市长、副市长、秘书长三个网页分组提取人物。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser"); source = final_url or str(page_rule.get("url", "")); rows = []
    for selector, duty in ((".sz", "市长"), (".fsz", "副市长"), (".msz", "秘书长")):
        group = soup.select_one(selector)
        if group is None: continue
        for anchor in group.select(".cont a[href], li a[href]"):
            name = clean_text(anchor.get_text(" ", strip=True)).replace(" ", "")
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                rows.append({"name": name, "duty": "", "evidence": duty,
                             "detail_url": urljoin(source, str(anchor.get("href") or "")),
                             "confidence": "high", "parser": "page_inline_nanyang_grouped_leaders_v1"})
    return rows

PAGE_RULE = {"rule_id": "3866", "page_type": "分组领导卡片", "load_mode": "静态HTML直出",
             "fetch_mode": "raw_http", "_fetch_mode_override": True, "extract_mode": "cards",
             "parser": "page_inline_nanyang_grouped_leaders_v1", "leader_region_selector": ".sz, .fsz, .msz",
             "name_selector": ".cont a", "detail_link_selector": ".cont a[href]",
             "locator_strategy": "custom_parse_page", "risk_flag": "", "confidence": "high"}

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")

if __name__ == "__main__": main()
