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
    "rule_id": "0855",
    "page_type": "人物列表完整页",
    "structure_group": "xinjiang_sasac_portrait_name_duty_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_xinjiang_sasac_portrait_name_duty_cards_v1",
    "leader_region_selector": ".lydimgul",
    "name_selector": ".lydimgul li中头像后的首个文本链接",
    "duty_selector": ".lydimgul li中第二个文本链接",
    "detail_link_selector": ".lydimgul li a:has(img)[href]",
    "content_scope": {"start_anchor": "首个头像人物卡片", "end_anchor": "末个头像人物卡片", "include_selectors": [".lydimgul li:has(a img)"], "exclude_selectors": ["内设处室", "直属单位", "HTML注释旧块"]},
    "detail_strategy": {"required": False, "mode": "list_item_dynamic_link", "detail_collector_type": "static_http", "detail_link_selector": ".lydimgul li a:has(img)[href]", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50},
    "risk_flag": "lydimgul复用于领导、处室和直属单位；只有含头像链接且另有姓名、职务两个文本链接的li才是人物",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".lydimgul", "name_selector": "li头像后首文本链接", "duty_selector": "li第二文本链接", "detail_link_selector": "li a:has(img)[href]", "content_scope": {"start_anchor": "首个头像卡片", "end_anchor": "末个头像卡片", "include_selectors": [".lydimgul li:has(a img)"], "exclude_selectors": ["处室单链接项", "直属单位单链接项"]}},
        "api": {"enabled": False, "reason": "当前静态HTML人物卡片直接提供头像、姓名、职务和详情链接"},
    },
}


def _clean_text(value: str) -> str:
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return " ".join(text.split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """只解析同时具有头像、姓名和职务链接的可见领导卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(".lydimgul li"):
        image_link = item.select_one("a[href]:has(img)")
        text_links = [a for a in item.select("a[href]") if _clean_text(a.get_text(" ", strip=True))]
        if image_link is None or len(text_links) < 2:
            continue
        name = re.sub(r"\s+", "", _clean_text(text_links[0].get_text(" ", strip=True)))
        duty = _clean_text(text_links[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": urljoin(base_url, str(image_link.get("href", ""))), "evidence": duty, "parser": "custom_xinjiang_sasac_portrait_name_duty_cards_v1", "selector_summary": ".lydimgul含头像人物卡片；文本链接姓名/职务"})
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
