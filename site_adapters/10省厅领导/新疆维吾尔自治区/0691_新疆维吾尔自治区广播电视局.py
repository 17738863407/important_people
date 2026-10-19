from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0691",
    "page_type": "人物列表完整页",
    "structure_group": "xinjiang_broadcast_primary_and_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_xinjiang_broadcast_primary_and_leader_cards_v1",
    "leader_region_selector": ".p30.ldypos",
    "name_selector": ".p20.ldy .ldy_p h3 a, ul.lydimgul li文本首链接",
    "duty_selector": ".p20.ldy .ldy_p > p:first-of-type, ul.lydimgul li文本第二链接",
    "detail_link_selector": ".p20.ldy .ldy_p h3 a[href], ul.lydimgul li a[href]",
    "content_scope": {"start_anchor": "主要领导", "end_anchor": "局领导末卡", "include_selectors": [".p20.ldy", "ul.lydimgul li"], "exclude_selectors": ["机构概况", "内设机构", "直属单位"]},
    "detail_strategy": {"required": False, "mode": "list_item_dynamic_link", "detail_collector_type": "static_http", "detail_link_selector": ".p20.ldy .ldy_p h3 a[href], ul.lydimgul li a[href]", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50},
    "risk_flag": "主要领导与其余局领导使用两种卡片结构；按1名主要领导后接局领导列表顺序解析，排除机构与直属单位栏目",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".p30.ldypos", "name_selector": ".p20.ldy h3 a或ul.lydimgul li文本首链接", "duty_selector": ".p20.ldy首个p或ul.lydimgul li文本第二链接", "detail_link_selector": "对应人物a[href]", "content_scope": {"start_anchor": "主要领导", "end_anchor": "局领导末项", "include_selectors": [".p20.ldy", "ul.lydimgul li"], "exclude_selectors": ["机构概况", "内设机构", "直属单位"]}},
        "api": {"enabled": False, "reason": "当前静态HTML两种卡片结构直接提供姓名、职务和详情链接"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split()).strip()


def _append(rows: list[dict[str, str]], seen: set[str], name: str, duty: str, detail_url: str) -> None:
    name = re.sub(r"\s+", "", _clean_text(name))
    duty = _clean_text(duty).removesuffix("。").strip()
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not duty or name in seen:
        return
    seen.add(name)
    rows.append({"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty, "parser": "custom_xinjiang_broadcast_primary_and_leader_cards_v1", "selector_summary": ".p20.ldy主要领导；ul.lydimgul局领导"})


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """先解析主要领导，再解析局领导卡片列表。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    primary = soup.select_one(".p20.ldy .ldy_p")
    if primary is not None:
        name_link = primary.select_one("h3 a[href]")
        duty_node = primary.select_one(":scope > p")
        if name_link is not None and duty_node is not None:
            _append(rows, seen, name_link.get_text(" ", strip=True), duty_node.get_text(" ", strip=True), urljoin(base_url, str(name_link.get("href", ""))))
    for item in soup.select("ul.lydimgul li"):
        text_links = [a for a in item.select("a[href]") if _clean_text(a.get_text(" ", strip=True))]
        if len(text_links) < 2:
            continue
        _append(rows, seen, text_links[0].get_text(" ", strip=True), text_links[1].get_text(" ", strip=True), urljoin(base_url, str(text_links[0].get("href", ""))))
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
