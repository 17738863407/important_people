from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag


def clean_text(value: str) -> str:
    """压缩页面排版空白，不改变职务原文语义。"""
    text = " ".join((value or "").replace("\xa0", " ").split())
    text = re.sub(r"\s+([，。；：、（）])", r"\1", text)
    return re.sub(r"([，。；：、（）])\s+", r"\1", text)


def clean_name(value: str) -> str:
    """移除姓名中的全角排版空格和零宽字符。"""
    return re.sub(r"[\s\u2000-\u200b\u3000]+", "", value or "")


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
    """按入口页面顺序提取全部领导卡片，并用详情页复核姓名与职务。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(".w-leader-cont")
    if region is None:
        raise RuntimeError("未找到卫健委领导卡片区域")

    records: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for card in region.select(".w-leader0img"):
        if is_hidden(card):
            continue
        name_node = card.select_one(".w-name")
        duty_node = card.select_one(".w-posi")
        anchor = card.find_parent("a", href=True)
        if name_node is None or duty_node is None or anchor is None:
            continue
        name = clean_name(name_node.get_text(" ", strip=True))
        duty = clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or name in seen_names:
            continue

        detail_url = urljoin(final_url, str(anchor.get("href", "")))
        detail_path = urlsplit(detail_url).path
        if not same_origin(final_url, detail_url) or not re.fullmatch(
            r"/zfxxgk/fdzdgknr/jgjj/ldxx/\d{6}/t\d{8}_\d+\.html",
            detail_path,
        ):
            raise RuntimeError(f"{name}详情路径不符合领导信息栏目结构")

        fetch_result = fetch_by_raw_requests(detail_url, timeout=30)
        detail_soup = BeautifulSoup(fetch_result.html, "lxml")
        detail_name_node = detail_soup.select_one(".w-name")
        detail_duty_node = detail_soup.select_one(".w-posi")
        detail_name = clean_name(detail_name_node.get_text(" ", strip=True) if detail_name_node else "")
        detail_duty = clean_text(detail_duty_node.get_text(" ", strip=True) if detail_duty_node else "")
        if detail_name != name or detail_duty != duty:
            raise RuntimeError(f"{name}目录卡片与详情姓名或职务不一致")

        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": fetch_result.final_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_shaanxi_cdc_leader_card_v2",
            }
        )
    return records


PAGE_RULE = {
    "rule_id": "2652",
    "page_type": "人物目录详情页",
    "structure_group": "shaanxi_health_leader_cards_full_page_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_shaanxi_cdc_leader_card_v2",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".w-leader-cont",
    "name_selector": ".w-leader0img .w-name",
    "duty_selector": ".w-leader0img .w-posi",
    "detail_link_selector": ".w-leader0img 的祖先 a[href]",
    "risk_flag": "按当前用户验收口径采集规则入口全部领导卡片；保持页面原序和完整原始职务，并逐卡进入详情页复核，不按职务关键词筛除人物",
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
