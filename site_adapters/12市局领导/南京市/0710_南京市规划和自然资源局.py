from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0710",
    "page_type": "人物列表完整页",
    "structure_group": "nanjing_planning_resources_iframe_heading_v2",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "custom_parse_page",
    "collector": "playwright_then_iframe_http",
    "parser": "page_nanjing_planning_resources_iframe_heading_v2",
    "leader_region_selector": "渲染后#xxgk_215当前链接 -> frame #znjj",
    "name_selector": "frame #znjj职务姓名标题段末尾姓名",
    "duty_selector": "同一标题段中姓名前的机构全称与原始职务",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "入口JavaScript改写iframe栏目地址，标题段后紧随工作分工，必须仅解析标题段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"frame_url_selector": "#xxgk_215 a[href]", "leader_region_selector": "#znjj", "row_selector": "#znjj p"},
        "api": {"enabled": False, "reason": "入口渲染后当前栏目链接指向frame静态正文，人物职务姓名在独立标题段"},
    },
}


def normalize_layout(text: str) -> str:
    """确定性清理富文本标题中的排版空白。"""
    value = re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：])\s*", r"\1", value)


def fetch_frame_html(main_html: str, final_url: str) -> str:
    """从渲染后的入口当前栏目链接动态发现并抓取frame正文。"""
    soup = BeautifulSoup(main_html, "html.parser")
    current_link = soup.select_one("#xxgk_215 a[href]")
    frame_url = urljoin(final_url, str(current_link.get("href", "")).strip()) if current_link else ""
    if not frame_url or frame_url == final_url:
        raise RuntimeError("渲染后的入口页未发现有效#xxgk_215当前栏目地址")
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
    """按frame标题段DOM顺序拆分完整原始职务和姓名。"""
    soup = BeautifulSoup(fetch_frame_html(html, final_url), "html.parser")
    region = soup.select_one("#znjj")
    if region is None:
        return []

    title_pattern = re.compile(
        r"^(?P<duty>南京市规划和自然资源局(?:党组成员、市土地储备中心主任|"
        r"党组成员、派驻纪检组组长|党组副书记、副局长|党组成员、副局长|"
        r"党组书记、局长|副局长|一级调研员))(?P<name>[\u4e00-\u9fff·]{2,8})$"
    )
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        text = normalize_layout(paragraph.get_text(" ", strip=True))
        match = title_pattern.fullmatch(text)
        if match is None:
            continue
        name = match.group("name")
        evidence = match.group("duty")
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
                "selector_summary": "Playwright渲染入口后动态发现frame；frame #znjj p按DOM顺序；仅解析机构全称+职务+姓名标题段，排除随后工作分工",
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
