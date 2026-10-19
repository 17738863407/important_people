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
    "rule_id": "2221",
    "domain": "rst.nmg.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "nmg_hrss_org_profile_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_nmg_hrss_org_profile_leader_cards_v1",
    "source_selector": "a.muluShow[data-url*='jggk']",
    "source_fetch_mode": "online",
    "leader_region_selector": ".leaderList",
    "leader_layout": {
        "primary_link_selector": "ul.leader1 li a[href]",
        "primary_duty_selector": "ul.leader1 + p",
        "primary_name_selector": "ul.leader1 + p + p",
        "secondary_item_selector": "ul.leader2 > li > a[href]",
        "secondary_duty_selector": "p:first-of-type",
        "secondary_name_selector": "p:last-of-type",
    },
    "detail_strategy": {"required": True, "mode": "card_anchor"},
    "risk_flag": "入口以jQuery.load载入机构简介子页；领导区第一人与其余卡片结构不同",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def fetch_source_html(source_url: str, fetch_mode: str) -> tuple[str, str]:
    """通过项目公共采集器取得入口动态指定的机构简介子页。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    result = fetch_html_with_strategy(source_url, strategy=fetch_mode)
    return result.html, result.final_url


def build_row(name: str, duty: str, detail_url: str) -> dict[str, str]:
    """校验强结构字段并构造单条人物记录。"""
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name):
        raise RuntimeError(f"领导卡片姓名异常：{name or '空值'}")
    if not duty:
        raise RuntimeError(f"{name}领导卡片职务为空")
    if not detail_url:
        raise RuntimeError(f"{name}领导卡片详情链接为空")
    return {"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url}


def parse_primary_leader(region: BeautifulSoup, source_url: str, layout: dict) -> dict[str, str]:
    """解析领导区中独立展示的首位人物。"""
    link = region.select_one(str(layout["primary_link_selector"]))
    duty_node = region.select_one(str(layout["primary_duty_selector"]))
    name_node = region.select_one(str(layout["primary_name_selector"]))
    if link is None or duty_node is None or name_node is None:
        raise RuntimeError("首位领导卡片结构不完整")
    return build_row(
        clean_text(name_node.get_text(" ", strip=True)),
        clean_text(duty_node.get_text(" ", strip=True)),
        urljoin(source_url, str(link.get("href") or "")),
    )


def parse_secondary_leaders(region: BeautifulSoup, source_url: str, layout: dict) -> list[dict[str, str]]:
    """按DOM顺序解析其余领导卡片。"""
    rows: list[dict[str, str]] = []
    for item in region.select(str(layout["secondary_item_selector"])):
        duty_node = item.select_one(str(layout["secondary_duty_selector"]))
        name_node = item.select_one(str(layout["secondary_name_selector"]))
        if duty_node is None or name_node is None:
            raise RuntimeError("领导卡片姓名或职务节点缺失")
        rows.append(
            build_row(
                clean_text(name_node.get_text(" ", strip=True)),
                clean_text(duty_node.get_text(" ", strip=True)),
                urljoin(source_url, str(item.get("href") or "")),
            )
        )
    return rows


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """动态发现机构简介子页并解析限定领导区域。"""
    entry_soup = BeautifulSoup(html, "html.parser")
    source_link = entry_soup.select_one(str(page_rule["source_selector"]))
    if source_link is None:
        raise RuntimeError("入口未找到机构简介子页链接")
    source_url = urljoin(final_url, str(source_link.get("data-url") or ""))
    source_html, source_final_url = fetch_source_html(source_url, str(page_rule["source_fetch_mode"]))
    source_soup = BeautifulSoup(source_html, "html.parser")
    region = source_soup.select_one(str(page_rule["leader_region_selector"]))
    if region is None:
        raise RuntimeError("机构简介子页未找到领导简介区域")

    layout = dict(page_rule["leader_layout"])
    rows = [parse_primary_leader(region, source_final_url, layout)]
    rows.extend(parse_secondary_leaders(region, source_final_url, layout))
    names = [row["name"] for row in rows]
    if len(names) != len(set(names)):
        raise RuntimeError("领导简介区域存在重复姓名")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
