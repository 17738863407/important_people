from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3082",
    "page_type": "人物列表完整页",
    "structure_group": "xinjiang_development_reform_primary_and_member_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_xinjiang_development_reform_primary_and_member_cards_v1",
    "leader_region_selector": ".zfld_zx, .zfld_fzx li",
    "name_selector": ".zfld_zx .zx_right h3 a[href], .zfld_fzx li p a[title][href]",
    "duty_selector": ".zfld_zx .fg p, .zfld_fzx li p:nth-of-type(2)",
    "detail_link_selector": ".zfld_zx .zx_right h3 a[href], .zfld_fzx li p a[title][href]",
    "content_scope": {
        "start_anchor": "主要领导卡",
        "end_anchor": "副职列表末项",
        "include_selectors": [".zfld_zx", ".zfld_fzx li"],
        "exclude_selectors": ["空占位项", "简历重复职务", "隐藏节点"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_item_dynamic_link",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".zfld_zx .zx_right h3 a[href], .zfld_fzx li p a[title][href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "主要领导与其他委领导使用两种结构，副职列表含一个空占位项；必须按主要领导后接列表顺序并跳过空项",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".zfld_zx, .zfld_fzx li",
            "name_selector": ".zx_right h3 a[href]或p a[title][href]",
            "duty_selector": ".fg p或第二个p",
            "detail_link_selector": "姓名链接",
            "content_scope": {
                "start_anchor": "主要领导卡",
                "end_anchor": "副职列表末项",
                "include_selectors": [".zfld_zx", ".zfld_fzx li"],
                "exclude_selectors": ["空占位项", "简历重复职务", "隐藏节点"],
            },
        },
        "api": {"enabled": False, "reason": "当前静态HTML两组委领导卡片直接提供姓名、职务和人物详情链接"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        if "zfld_zx" in classes or "zfld_fzx" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def _detail_url(base_url: str, href: str) -> str:
    href = href.strip()
    if not href or href.startswith(("#", "javascript:", "mailto:")):
        return ""
    resolved = urljoin(base_url, href)
    if resolved.split("#", 1)[0].rstrip("/") == base_url.split("#", 1)[0].rstrip("/"):
        return ""
    parsed = urlparse(resolved)
    return resolved if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    cards = soup.select(".zfld_zx") + soup.select(".zfld_fzx li")
    for card in cards:
        if _is_hidden(card):
            continue
        if "zfld_zx" in {str(value) for value in card.get("class", [])}:
            name_link = card.select_one(".zx_right h3 a[href]")
            duty_node = card.select_one(".fg p")
        else:
            name_link = card.select_one("p a[title][href]")
            paragraphs = card.select("p")
            duty_node = paragraphs[1] if len(paragraphs) > 1 else None
        if name_link is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", _clean_text(name_link.get_text(" ", strip=True)))
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,30}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": _detail_url(base_url, str(name_link.get("href", ""))),
                "evidence": duty,
                "parser": "custom_xinjiang_development_reform_primary_and_member_cards_v1",
                "selector_summary": "主要领导zx_right/fg；其他领导姓名链接/第二p职务",
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
