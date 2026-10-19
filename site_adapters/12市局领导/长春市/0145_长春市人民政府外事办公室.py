from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0145",
    "page_type": "人物列表完整页",
    "structure_group": "changchun_fao_visible_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "page_inline_changchun_fao_visible_leader_cards_v1",
    "leader_region_selector": "ul.leader > li",
    "name_selector": "dd.d_center h2 a[href]",
    "duty_selector": "dd.d_center h2 a[href]",
    "detail_link_selector": "dd.d_center h2 a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["ul.leader"],
        "exclude_selectors": ["iframe"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "raw_http",
        "detail_link_selector": "dd.d_center h2 a[href]",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": (
        "原始HTTP响应包含权威人物卡片；页面模板含浏览器版本提示，会触发online有效性误判；"
        "页面另含与领导列表无关的认证iframe"
    ),
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_visible_leader_cards",
    "locator": {
        "css": {
            "leader_region_selector": "ul.leader > li",
            "title_link_selector": "dd.d_center h2 a[href]",
        },
        "api": {
            "enabled": False,
            "reason": "权威入口的原始HTML已经稳定包含姓名、职务和人物详情链接",
        },
        "migration": {
            "source": "legacy_inline_parser",
            "verified_status": "verified_current_raw_http",
            "behavior_changed": True,
        },
    },
}


def clean_text(text: str) -> str:
    """清理HTML排版空白，不改变网页文字语义。"""
    return " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())


def clean_name(text: str) -> str:
    """合并姓名因网页排版产生的字间空格。"""
    return clean_text(text).replace(" ", "")


def split_title(title: str) -> tuple[str, str]:
    """按卡片标题中的明确冒号边界拆分原始职务和姓名。"""
    normalized = clean_text(title)
    for separator in ("：", ":"):
        if separator in normalized:
            duty, name = normalized.split(separator, 1)
            return clean_text(duty), clean_name(name)
    return "", ""


def is_hidden(node) -> bool:
    """排除当前节点或祖先上明确隐藏的人物备用DOM。"""
    current = node
    while current is not None and getattr(current, "attrs", None) is not None:
        attrs = current.attrs
        style = str(attrs.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in attrs.get("class", [])}
        if (
            "hidden" in attrs
            or str(attrs.get("aria-hidden", "")).lower() == "true"
            or "display:none" in style
            or "visibility:hidden" in style
            or classes.intersection({"hidden", "hide"})
        ):
            return True
        current = current.parent
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按网页顺序解析可见人物卡片及其一一对应的详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    base_url = final_url or page_rule["url"]

    for item in soup.select(page_rule["leader_region_selector"]):
        if is_hidden(item):
            continue
        title_link = item.select_one("dd.d_center h2 a[href]")
        if title_link is None or is_hidden(title_link):
            continue
        duty, name = split_title(title_link.get_text(" ", strip=True))
        href = clean_text(title_link.get("href", ""))
        if not name or not duty or not href:
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(base_url, href),
                "source_text": duty,
                "method": page_rule["parser"],
                "note": (
                    "strategy=custom_parse_page；leader=ul.leader > li；"
                    "name/duty=card_title_split_colon；detail=same_card_title_link；"
                    "hidden_nodes=excluded"
                ),
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
