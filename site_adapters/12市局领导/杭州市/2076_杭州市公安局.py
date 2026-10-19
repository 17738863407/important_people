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
    "rule_id": "2076",
    "page_type": "人物目录详情页",
    "structure_group": "hangzhou_public_security_visible_leader_block",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "hangzhou_public_security_visible_leaders_v3",
    "leader_region_selector": "div.zfxxgk_item（标题为本机关负责人）",
    "name_selector": "div.zfxxgk_zdgkc > ul > li > a",
    "duty_selector": "td.title + td.list",
    "detail_link_selector": "a[href*='art_1229441199_']",
    "content_scope": {
        "start_anchor": "本机关负责人",
        "end_anchor": "本机关简介",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "raw_http",
        "detail_link_selector": "div.zfxxgk_zdgkc > ul > li > a[href*='art_1229441199_']",
        "detail_name_selector": "tr:has(td.title) td.list",
        "detail_duty_selector": "tr:has(td.title) td.list",
        "detail_content_selector": "table",
        "max_detail_links": 10,
    },
    "risk_flag": "当前“更多”栏目已返回404，禁止调用其后台构建接口或采集接口残留人物；只采集机构介绍入口直接展示的五人并逐页校验",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.zfxxgk_item（标题为本机关负责人）",
            "name_selector": "div.zfxxgk_zdgkc > ul > li > a",
            "duty_selector": "td.title + td.list",
            "detail_link_selector": "div.zfxxgk_zdgkc > ul > li > a[href*='art_1229441199_']",
            "content_scope": {
                "start_anchor": "本机关负责人",
                "end_anchor": "本机关简介",
                "include_selectors": [],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "更多栏目404，后台接口数据不再作为当前有效页面证据"},
        "migration": {
            "source": "current_visible_entry_and_details",
            "verified_status": "verified_online",
            "behavior_changed": True,
        },
    },
}


def clean_text(value: str) -> str:
    """清理详情页字段中的纯排版空白。"""
    text = re.sub(r"[\s\u3000\u00a0\u2000-\u200b]+", " ", str(value or "")).strip()
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return re.sub(r"\s*([，、；：])\s*", r"\1", text)


def parse_detail(html: str, fallback_name: str) -> tuple[str, str]:
    """从人物详情表格的“姓名”“职务”强结构字段取值。"""
    soup = BeautifulSoup(html, "html.parser")
    values: dict[str, str] = {}
    for row in soup.select("tr"):
        label_node = row.select_one("td.title")
        value_node = row.select_one("td.list")
        if label_node is None or value_node is None:
            continue
        label = re.sub(r"\s+", "", label_node.get_text(" ", strip=True)).rstrip("：:")
        values.setdefault(label, clean_text(value_node.get_text(" ", strip=True)))
    name = re.sub(r"\s+", "", values.get("姓名", fallback_name))
    return name, values.get("职务", "").rstrip("。；; ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """只按当前入口页直接展示的负责人顺序逐页取得姓名和职务。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    entry = BeautifulSoup(html, "html.parser")
    leader_blocks = []
    for block in entry.select("div.zfxxgk_item"):
        title_node = block.select_one("div.zfxxgk_zdgktit span")
        title = clean_text(title_node.get_text(" ", strip=True) if title_node else "")
        if title == "本机关负责人":
            leader_blocks.append(block)
    if len(leader_blocks) != 1:
        raise RuntimeError(f"当前入口页“本机关负责人”区域数量异常：{len(leader_blocks)}")

    leader_block = leader_blocks[0]
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    detail_links = leader_block.select(
        "div.zfxxgk_zdgkc > ul > li > a[href*='art_1229441199_']"
    )
    if not detail_links:
        raise RuntimeError("当前入口页“本机关负责人”区域没有直接展示的人物详情链接")
    for link in detail_links:
        fallback_name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        detail_url = urljoin(base_url, str(link.get("href") or ""))
        if detail_url in seen_urls:
            continue
        try:
            result = fetch_by_raw_requests(detail_url)
            name, duty = parse_detail(result.html, fallback_name)
            detail_url = result.final_url
        except Exception as error:
            raise RuntimeError(f"{fallback_name or detail_url} 详情页采集或解析失败：{error}") from error
        if name != fallback_name:
            raise RuntimeError(f"详情页姓名不匹配：目录={fallback_name}，详情={name or '<空>'}")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name) or not duty:
            raise RuntimeError(f"{fallback_name} 详情页姓名或职务字段异常")
        seen_urls.add(detail_url)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "entry=本机关负责人可见列表；detail=姓名/职务表格字段",
            }
        )
    if len(rows) != len(detail_links):
        raise RuntimeError("入口页可见负责人列表与详情页验收数量不一致")
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
