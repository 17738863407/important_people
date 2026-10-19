from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0733",
    "page_type": "人物列表完整页",
    "structure_group": "nanjing_government_affairs_iframe_profile_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_then_iframe_http",
    "parser": "page_nanjing_government_affairs_iframe_profile_v2",
    "leader_region_selector": "iframe#dataList -> #heightbox1",
    "name_selector": "#heightbox1人物简介段strong",
    "duty_selector": "同一人物简介段内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "领导简介位于共享iframe首个标签页，必须动态解析src并排除后续分工段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"frame_selector": "iframe#dataList[src]", "leader_region_selector": "#heightbox1", "row_selector": "#heightbox1 p"},
        "api": {"enabled": False, "reason": "入口静态HTML直接给出iframe地址，frame首个标签页直接包含人物简介段"},
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    value = re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()
    return re.sub(r"\s*([、，。；：])\s*", r"\1", value)


def fetch_frame_html(main_html: str, final_url: str) -> str:
    """从入口iframe元素动态解析并抓取frame正文。"""
    soup = BeautifulSoup(main_html, "html.parser")
    frame = soup.select_one("iframe#dataList[src]")
    frame_url = urljoin(final_url, str(frame.get("src", "")).strip()) if frame else ""
    if not frame_url or frame_url == final_url:
        raise RuntimeError("入口页未发现有效的iframe#dataList地址")
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
    """按frame首个标签页人物简介段顺序提取姓名和完整“现任……”句。"""
    soup = BeautifulSoup(fetch_frame_html(html, final_url), "html.parser")
    region = soup.select_one("#heightbox1")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        evidence_match = re.search(r"现任[^。]*。", text)
        strong = paragraph.find("strong")
        if strong is None or evidence_match is None:
            continue
        name = re.sub(r"\s+", "", strong.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        evidence = re.sub(r"^现任\s*", "", evidence_match.group(0)).removesuffix("。")
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "入口iframe#dataList动态取src；frame #heightbox1 p按DOM顺序；strong姓名与同段完整现任句",
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
