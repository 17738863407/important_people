from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0668",
    "page_type": "人物列表完整页",
    "structure_group": "nanjing_defense_mobilization_iframe_fields_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_then_iframe_http",
    "parser": "page_nanjing_defense_mobilization_iframe_fields_v2",
    "leader_region_selector": "iframe#dataList正文",
    "name_selector": "姓名字段",
    "duty_selector": "同一人物块的职务字段",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "领导字段位于共享iframe，必须从入口DOM动态解析src并按字段顺序关联",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"frame_selector": "iframe#dataList[src]", "row_selector": "frame正文p中的姓名与职务字段"},
        "api": {"enabled": False, "reason": "入口静态HTML直接给出iframe地址，frame静态正文含明确姓名和职务字段"},
    },
}


def normalize_layout(text: str) -> str:
    """确定性清理富文本字段中的排版空白。"""
    value = re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
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
    """按frame字段DOM顺序关联姓名及紧随其后的职务原文。"""
    soup = BeautifulSoup(fetch_frame_html(html, final_url), "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    pending_name = ""
    for paragraph in soup.select("p"):
        text = normalize_layout(paragraph.get_text(" ", strip=True))
        name_match = re.fullmatch(r"姓名：(?P<name>[\u4e00-\u9fff·]{2,8})", text)
        if name_match is not None:
            pending_name = name_match.group("name")
            continue
        duty_match = re.fullmatch(r"职务：(?P<duty>.+)", text)
        if not pending_name or duty_match is None or pending_name in seen:
            continue
        evidence = duty_match.group("duty").strip("，。；")
        if not evidence:
            continue
        seen.add(pending_name)
        rows.append(
            {
                "name": pending_name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "入口iframe#dataList动态取src；frame p按DOM顺序；姓名字段与紧随其后的职务字段关联",
            }
        )
        pending_name = ""
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
