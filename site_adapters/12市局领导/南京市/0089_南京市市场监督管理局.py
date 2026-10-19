from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0089",
    "page_type": "人物列表完整页",
    "structure_group": "nanjing_market_regulation_iframe_current_sentence_v2",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "custom_parse_page",
    "collector": "playwright_then_iframe_http",
    "parser": "page_nanjing_market_regulation_iframe_current_sentence_v2",
    "leader_region_selector": "iframe#dataList -> #jgcon3 .view",
    "name_selector": "iframe正文人物段冒号前姓名",
    "duty_selector": "同一人物段内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "入口页通过JavaScript导航iframe且iframe src属性保持为空，需从渲染后的当前栏目链接发现frame URL",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "frame_selector": "iframe#dataList",
            "frame_url_fallback_selector": "#xxgk_215 a[href]",
            "leader_region_selector": "#jgcon3 .view",
            "row_selector": "#jgcon3 .view直接子级p或div",
        },
        "api": {"enabled": False, "reason": "入口页渲染后动态发现iframe栏目地址，再抓取frame静态正文"},
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def fetch_frame_html(main_html: str, final_url: str) -> str:
    """从渲染后的入口DOM动态发现当前iframe栏目地址并抓取正文。"""
    soup = BeautifulSoup(main_html, "html.parser")
    frame = soup.select_one("iframe#dataList")
    frame_url = urljoin(final_url, str(frame.get("src", "")).strip()) if frame else ""
    if not frame_url or frame_url == final_url:
        current_link = soup.select_one("#xxgk_215 a[href]")
        frame_url = urljoin(final_url, str(current_link.get("href", "")).strip()) if current_link else ""
    if not frame_url or frame_url == final_url:
        raise RuntimeError("渲染后的入口DOM未发现当前领导信息iframe栏目地址")

    response = requests.get(
        frame_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": final_url,
        },
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按iframe正文DOM顺序提取姓名和当前人物段内完整“现任……”句。"""
    content_html = fetch_frame_html(html, final_url)
    soup = BeautifulSoup(content_html, "html.parser")
    region = soup.select_one("#jgcon3 .view")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for node in region.find_all(["p", "div"], recursive=False):
        text = normalize_space(node.get_text(" ", strip=True))
        name_match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,8})[：:]", text)
        evidence_match = re.search(r"现任[^。]*。", text)
        if name_match is None or evidence_match is None:
            continue
        name = name_match.group("name")
        evidence = normalize_space(evidence_match.group(0))
        evidence = re.sub(r"^现任\s*", "", evidence).rstrip("。")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "渲染入口#xxgk_215当前链接动态发现frame；#jgcon3 .view直接子级按DOM顺序；冒号前姓名与同段完整现任句",
            }
        )
    return rows


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
