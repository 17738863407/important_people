from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按市政府页中经标题划分的领导卡片顺序抽取。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".szf_con")
    if region is None:
        raise RuntimeError("未找到市政府领导分组区域")

    base_url = final_url or str(page_rule.get("url", ""))
    allowed_duties = {"市长", "副市长", "秘书长"}
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for group in region.select(":scope > .szf_tit1"):
        title_node = group.select_one(":scope > .szf_tit_l1")
        duty = re.sub(r"[\s：:]", "", title_node.get_text(" ", strip=True) if title_node else "")
        if duty not in allowed_duties:
            continue
        for link in group.select(":scope > .szf_tit_r1 > ul#columns > li > p > a[href]"):
            name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
            href = str(link.get("href") or "").strip()
            detail_url = urljoin(base_url, href) if href else ""
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                continue
            if name in seen_names or urlparse(detail_url).scheme not in {"http", "https"}:
                continue
            seen_names.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": "",
                    "evidence": duty,
                    "detail_url": detail_url,
                    "confidence": "high",
                    "parser": "page_inline_nanping_government_groups_v1",
                }
            )

    if not rows:
        raise RuntimeError("市政府领导分组未提取到有效人物")
    return rows

PAGE_RULE = {"rule_id": "3865", "page_type": "市政府领导分组页", "load_mode": "静态HTML",
             "fetch_mode": "online", "extract_mode": "scoped_grouped_cards",
             "parser": "page_inline_nanping_government_groups_v1", "leader_region_selector": ".szf_con",
             "name_selector": ".szf_tit_r1 > ul#columns > li > p > a[href]", "duty_selector": ".szf_tit_l1",
             "detail_link_selector": ".szf_tit_r1 > ul#columns > li > p > a[href]",
             "locator_strategy": "custom_parse_page", "risk_flag": "只解析市长、副市长、秘书长直属卡片组", "confidence": "high"}

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")

if __name__ == "__main__": main()
