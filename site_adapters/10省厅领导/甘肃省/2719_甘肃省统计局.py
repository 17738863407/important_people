from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag


def clean_text(value: str) -> str:
    """压缩人物卡片的排版空白，不改变原文语义。"""
    text = " ".join((value or "").replace("\u3000", " ").replace("\xa0", " ").split())
    text = re.sub(r"\s+([，。；：、（）])", r"\1", text)
    return re.sub(r"([，。；：、（）])\s+", r"\1", text)


def is_hidden(node: Tag) -> bool:
    """排除节点及祖先明确隐藏的备用 DOM。"""
    current: Tag | None = node
    while current is not None:
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        style = re.sub(r"\s+", "", str(current.get("style", "")).lower())
        if "display:none" in style or "visibility:hidden" in style:
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False


def same_origin(reference_url: str, candidate_url: str) -> bool:
    reference = urlsplit(reference_url)
    candidate = urlsplit(candidate_url)
    return (reference.scheme, reference.netloc) == (candidate.scheme, candidate.netloc)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析渲染后的领导卡片；分工正文不作为主职务依据。"""
    soup = BeautifulSoup(html, "lxml")
    leader_list = soup.select_one("ul#list.ldjj_list")
    if leader_list is None:
        raise RuntimeError("未找到渲染后的领导简介列表")

    records: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for card in leader_list.select(":scope > li"):
        if is_hidden(card):
            continue
        anchor = card.select_one(":scope > a[href]")
        name_node = card.select_one(":scope > a[href] .text > p.title")
        duty_node = card.select_one(":scope > a[href] .text > p.desc")
        content_node = card.select_one(":scope > a[href] .text > div.content")
        if anchor is None or name_node is None or duty_node is None or content_node is None:
            continue

        name = clean_text(name_node.get_text(" ", strip=True))
        duty = clean_text(duty_node.get_text(" ", strip=True))
        content = clean_text(content_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or name in seen_names or not duty:
            continue
        if not content.startswith(f"简历——{name}") or f"现任{duty}。" not in content:
            raise RuntimeError(f"{name}卡片简介无法回指当前职务")

        detail_url = urljoin(final_url, str(anchor.get("href", "")))
        detail_path = urlsplit(detail_url).path
        if not same_origin(final_url, detail_url) or not re.fullmatch(
            r"/tjj/c109477/\d{6}/\d+\.shtml",
            detail_path,
        ):
            raise RuntimeError(f"{name}详情路径不符合当前领导栏目结构")

        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_gansu_stats_leader_cards_v1",
            }
        )
    return records


PAGE_RULE = {
    "rule_id": "2719",
    "page_type": "人物目录详情页",
    "structure_group": "gansu_stats_rendered_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "page_inline_gansu_stats_leader_cards_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "ul#list.ldjj_list",
    "name_selector": ":scope > li > a .text > p.title",
    "duty_selector": ":scope > li > a .text > p.desc",
    "detail_link_selector": ":scope > li > a[href]",
    "risk_flag": "普通 HTTP 返回 412；领导卡片同时含简历和分工，仅独立职务节点进入依据说明",
    "confidence": "high",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
