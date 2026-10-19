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
    "rule_id": "3815", "domain": "www.dingxi.gov.cn", "page_type": "同页四套班子分职务名单",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_dingxi_government_v1",
    "leader_region_selector": ".zfxxzdlist", "name_selector": ".gs_jg a[href]", "duty_selector": ".jg_tit",
    "detail_link_selector": ".gs_jg a[href]", "content_scope": {"start_anchor": "市政府领导", "end_anchor": "市政协领导", "include_selectors": [".zfxxzdlist"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "同页四套班子，按分组标题精确选择市政府区域", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = next((node for node in soup.select(".zfxxzdlist") if clean_text((node.select_one(".zfxxgk_zdgktit") or node).get_text(" ", strip=True)) == "市政府领导"), None)
    if not region:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    current_duty = ""
    rows: list[dict[str, str]] = []
    for child in region.children:
        if not isinstance(child, Tag):
            continue
        if "jg_tit" in (child.get("class") or []):
            current_duty = clean_text(child.get_text(" ", strip=True))
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
