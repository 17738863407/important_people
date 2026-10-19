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
    "rule_id": "0857",
    "page_type": "人物列表完整页",
    "structure_group": "yunnan_sasac_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_yunnan_sasac_leader_cards_v1",
    "leader_region_selector": ".lzy-leader a.leader-item[href]",
    "name_selector": ".lzy-leader a.leader-item[href] .name",
    "duty_selector": ".lzy-leader a.leader-item[href] .post",
    "detail_link_selector": ".lzy-leader a.leader-item[href]",
    "content_scope": {
        "start_anchor": "委领导首卡",
        "end_anchor": "委领导末卡",
        "include_selectors": [".lzy-leader a.leader-item[href]"],
        "exclude_selectors": ["隐藏节点", "其他栏目"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_item_dynamic_link",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".lzy-leader a.leader-item[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "委领导卡片字段明确；必须限定.lzy-leader并保持卡片DOM顺序",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".lzy-leader a.leader-item[href]",
            "name_selector": ".name",
            "duty_selector": ".post",
            "detail_link_selector": "当前卡片href",
            "content_scope": {
                "start_anchor": "委领导首卡",
                "end_anchor": "委领导末卡",
                "include_selectors": [".lzy-leader a.leader-item[href]"],
                "exclude_selectors": ["隐藏节点", "其他栏目"],
            },
        },
        "api": {"enabled": False, "reason": "当前静态HTML委领导卡片直接提供姓名、职务和人物详情链接"},
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
        if "lzy-leader" in classes:
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
    for card in soup.select(".lzy-leader a.leader-item[href]"):
        if _is_hidden(card):
            continue
        name_node = card.select_one(".name")
        duty_node = card.select_one(".post")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True)))
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": _detail_url(base_url, str(card.get("href", ""))),
                "evidence": duty,
                "parser": "custom_yunnan_sasac_leader_cards_v1",
                "selector_summary": ".lzy-leader a.leader-item；.name姓名；.post职务",
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
