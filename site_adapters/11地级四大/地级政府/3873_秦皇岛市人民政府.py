from __future__ import annotations
import re
import sys
from pathlib import Path

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按政府组成人员正文逐段解析姓名与网页原始职务。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser"); rows = []
    scope = soup.select_one(".article-content")
    if scope is None: return rows
    for paragraph in scope.select("p"):
        raw = paragraph.get_text(" ", strip=True).replace("\xa0", " ")
        match = re.match(r"^(.+?)[\s\u3000]{2,}(.+?)$", raw)
        if not match: continue
        name = re.sub(r"[\s\u3000]+", "", match.group(1))
        evidence = clean_text(match.group(2)).replace(" ", "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) and evidence:
            rows.append({"name": name, "duty": "", "evidence": evidence, "detail_url": "",
                         "confidence": "high", "parser": "page_inline_qinhuangdao_constituents_paragraphs_v1"})
    return rows

PAGE_RULE = {"rule_id": "3873", "page_type": "政府组成人员正文", "load_mode": "静态HTML直出",
             "fetch_mode": "playwright", "_fetch_mode_override": True, "extract_mode": "paragraph_pairs",
             "parser": "page_inline_qinhuangdao_constituents_paragraphs_v1",
             "leader_region_selector": ".article-content", "name_selector": ".article-content p",
             "duty_selector": ".article-content p", "locator_strategy": "custom_parse_page",
             "risk_flag": "入口为政府组成人员名录，按页面范围保留全部成员", "confidence": "high"}

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")

if __name__ == "__main__": main()
