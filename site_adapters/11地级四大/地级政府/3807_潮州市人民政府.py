from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3807", "domain": "www.chaozhou.gov.cn", "page_type": "领导卡片列表",
    "load_mode": "浏览器渲染DOM", "fetch_mode": "online", "force_browser": True, "extract_mode": "list_direct",
    "collector": "browser_dom", "parser": "page_inline_chaozhou_government_v1",
    "leader_region_selector": "#tab_ldxx", "name_selector": "span a[href]", "duty_selector": "span b",
    "detail_link_selector": "span a[href]", "content_scope": {"start_anchor": "市政府", "end_anchor": "", "include_selectors": ["#tab_ldxx"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "源码尾部含注释掉的历史人物节点，BeautifulSoup结构选择只处理可见DOM", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#tab_ldxx")
    if not region:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for span in region.select("span"):
        duty_node = span.select_one("b")
        link = span.select_one("a[href]")
        if not duty_node or not link:
            continue
        duty = clean_text(duty_node.get_text(" ", strip=True)).rstrip("：:")
        name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
        if duty in {"市长", "副市长", "秘书长"} and re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, str(link.get("href", "")).strip()), "confidence": "high", "parser": str(page_rule.get("parser", ""))})
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
