from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3111",
    "page_type": "多人物详情合并页",
    "structure_group": "yunnan_agricultural_academy_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "force_browser": True,
    "playwright_stealth_profile": 1,
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "custom_yunnan_agricultural_academy_leader_cards_v2",
    "leader_region_selector": "div.subPage.wrap dl.imgText1 > dd",
    "name_selector": ".title",
    "duty_selector": ".textC中的现任句",
    "detail_link_selector": "a.con[href]",
    "content_scope": {
        "start_anchor": "领导介绍首张卡片",
        "end_anchor": "领导介绍末张卡片",
        "include_selectors": ["div.subPage.wrap dl.imgText1 > dd"],
        "exclude_selectors": ["院属科研机构", "院属职能处室", "友情链接", "页脚"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_links_only",
        "detail_collector_type": "browser_dom",
        "detail_link_selector": "a.con[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 20,
    },
    "risk_flag": "HTTP仅返回云锁验证脚本，须强制浏览器；末张卡初始为WOW滚动动画暂态隐藏，滚动后已验证可见",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.subPage.wrap dl.imgText1 > dd",
            "name_selector": ".title",
            "duty_selector": ".textC中的现任句",
            "detail_link_selector": "a.con[href]",
            "content_scope": {
                "start_anchor": "领导介绍首张卡片",
                "end_anchor": "领导介绍末张卡片",
                "include_selectors": ["div.subPage.wrap dl.imgText1 > dd"],
                "exclude_selectors": ["院属科研机构", "院属职能处室", "友情链接", "页脚"],
            },
        },
        "api": {"enabled": False, "reason": "当前业务数据由云锁后的浏览器DOM人物卡片直接提供"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(
        str(value or "")
        .replace("\u200b", "")
        .replace("\u3000", " ")
        .replace("\xa0", " ")
        .split()
    )


def _is_pending_scroll_animation(node: Tag) -> bool:
    classes = {str(value).lower() for value in node.get("class", [])}
    return (
        node.name == "dd"
        and "wow" in classes
        and "fadeinup" in classes
        and node.find_parent("dl", class_="imgText1") is not None
    )


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "hidden" in classes:
            return True
        if "visibility:hidden" in style and not _is_pending_scroll_animation(current):
            return True
        if "subpage" in classes and "wrap" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select("div.subPage.wrap dl.imgText1 > dd"):
        if _is_hidden(card):
            continue
        link = card.select_one("a.con[href]")
        name_node = card.select_one(".title")
        profile_node = card.select_one(".textC")
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        profile = _clean_text(profile_node.get_text(" ", strip=True) if profile_node else "")
        current_duty_match = re.search(r"现任[^。]*。", profile)
        href = str(link.get("href") or "").strip() if link else ""
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name)
            or current_duty_match is None
            or name in seen
        ):
            continue
        evidence = re.sub(
            r"^现任(?:职务)?(?:\s*[：:]\s*)?\s*",
            "",
            current_duty_match.group(0),
            count=1,
        )
        detail_url = urljoin(final_url, href) if href and not href.startswith(("#", "javascript:", "mailto:")) else ""
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": "custom_yunnan_agricultural_academy_leader_cards_v2",
                "selector_summary": "div.subPage.wrap dl.imgText1 > dd；.title姓名；.textC现任句；a.con[href]详情",
            }
        )
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
