from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3799", "domain": "www.jlbc.gov.cn", "page_type": "分职务名单",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_baicheng_government_v1",
    "leader_region_selector": ".l_main_box .row", "name_selector": "ul li a[href]", "duty_selector": ".tit h2",
    "detail_link_selector": "ul li a[href]", "content_scope": {"start_anchor": "市长", "end_anchor": "", "include_selectors": [".l_main_box"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "市长栏目当前仅有注释中的旧姓名，不抽取注释；只处理可见副市长和秘书长名单", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".l_main_box .row")
    if not region:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    current_duty = ""
    rows: list[dict[str, str]] = []
    for child in region.children:
        if not isinstance(child, Tag):
            continue
        heading = child.select_one("h2") if child.name == "div" else None
        if heading:
            current_duty = clean_text(heading.get_text(" ", strip=True))
            continue
        if child.name != "ul" or not current_duty:
            continue
        for link in child.select("li a[href]"):
            name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
                rows.append({"name": name, "duty": current_duty, "evidence": current_duty, "detail_url": urljoin(base_url, str(link.get("href", ""))), "confidence": "high", "parser": str(page_rule.get("parser", ""))})
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
