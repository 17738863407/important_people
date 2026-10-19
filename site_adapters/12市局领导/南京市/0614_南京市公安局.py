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

def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)
    return re.sub(r"\s+([，。；：、（）])", r"\1", text)


def is_name_text(text: str) -> bool:
    normalized = clean_text(text).replace("（照片略）", "").strip()
    return bool(re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", normalized))


def parse_leader_html(html: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    current_name = ""

    for paragraph in soup.select("#heightbox1 .view p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        if "市公安局内设机构及职能" in text:
            break
        if is_name_text(text):
            current_name = clean_text(text).replace("（照片略）", "").strip()
            continue
        if current_name:
            rows.append(
                {
                    "organization": str(page_rule.get("organization", "")),
                    "url": str(page_rule.get("url", "")),
                    "name": current_name,
                    "duty": text,
                    "detail_url": "",
                    "evidence": text,
                    "confidence": "high",
                    "parser": "page_inline_nanjing_police_iframe_leaders_v1",
                }
            )
            current_name = ""
    return rows


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """动态取得机构概况 iframe，并解析领导姓名后的首个职务段。"""
    rows = parse_leader_html(html, page_rule)
    if rows:
        return rows

    soup = BeautifulSoup(html, "html.parser")
    iframe = soup.select_one('iframe[name="dataList"], iframe#dataList')
    iframe_url = ""
    if iframe and iframe.get("src"):
        iframe_url = urljoin(str(page_rule.get("url", "")), str(iframe.get("src")))
    if iframe_url:
        from crawler_core.fetcher import fetch_html_with_strategy

        iframe_result = fetch_html_with_strategy(iframe_url, "raw_http")
        return parse_leader_html(iframe_result.html, page_rule)
    return []


PAGE_RULE = {
    "rule_id": "0614",
    "page_type": "人物列表完整页",
    "structure_group": "nanjing_police_iframe_leader_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_nanjing_police_iframe_leaders_v1",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "领导信息位于入口页动态声明的同站 iframe；职务后另有分工段，不并入依据说明",
    "confidence": "high",
}


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
