from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2038",
    "page_type": "人物列表完整页",
    "structure_group": "nanjing_agriculture_current_profile_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_then_current_section_http",
    "parser": "page_nanjing_agriculture_current_profile_v2",
    "leader_region_selector": "#xxgk_215当前链接 -> #jgcon3",
    "name_selector": "#jgcon3人物简介段首个逗号前",
    "duty_selector": "同一人物简介段内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "入口iframe初始src为空，必须从当前概况栏目链接动态发现正文；现任句后另有工作分工段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"content_url_selector": "#xxgk_215 a[href]", "leader_region_selector": "#jgcon3", "row_selector": "#jgcon3 p"},
        "api": {"enabled": False, "reason": "入口当前概况栏目链接和正文均由静态HTML直接提供"},
    },
}


def normalize_layout(text: str) -> str:
    """确定性清理富文本编辑器产生的中文排版空白。"""
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：])\s*", r"\1", value)


def clean_evidence(value: str) -> str:
    """删除完整现任句的固定前缀和纯句末句号。"""
    return re.sub(r"。$", "", re.sub(r"^现任\s*", "", normalize_layout(value))).strip()


def fetch_content_html(main_html: str, final_url: str) -> str:
    """动态发现当前概况栏目地址并通过公共增强请求抓取正文。"""
    soup = BeautifulSoup(main_html, "html.parser")
    current_link = soup.select_one("#xxgk_215 a[href]")
    content_url = urljoin(final_url, str(current_link.get("href", "")).strip()) if current_link else ""
    if not content_url or content_url == final_url:
        raise RuntimeError("入口页未发现有效的#xxgk_215当前栏目地址")

    from crawler_core.fetcher import fetch_html_with_strategy

    return fetch_html_with_strategy(content_url, strategy="requests").html


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按#jgcon3人物简介段顺序提取姓名和完整现任句。"""
    soup = BeautifulSoup(fetch_content_html(html, final_url), "html.parser")
    region = soup.select_one("#jgcon3")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        text = normalize_layout(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,8})，", text)
        evidence_match = re.search(r"现任[^。]*。", text)
        if name_match is None or evidence_match is None:
            continue
        name = name_match.group("name")
        if name in seen:
            continue
        seen.add(name)
        evidence = clean_evidence(evidence_match.group(0))
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "入口#xxgk_215当前链接动态取正文；#jgcon3 p按DOM顺序提取段首姓名与完整现任句",
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
