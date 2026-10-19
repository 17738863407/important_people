from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2204",
    "page_type": "人物列表完整页",
    "structure_group": "nanjing_hrss_current_profile_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_then_rewritten_section_http",
    "parser": "page_nanjing_hrss_current_profile_v2",
    "leader_region_selector": "#xxgk_215脚本改写地址 -> #nsks",
    "name_selector": "#nsks人物简介段首个逗号前",
    "duty_selector": "同一人物简介段内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "入口iframe初始src为空且静态栏目href会被脚本改写，必须优先解析#xxgk_215的href赋值",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"content_url_selector": "#xxgk_215 a[href]及其脚本href赋值", "leader_region_selector": "#nsks", "row_selector": "#nsks p"},
        "api": {"enabled": False, "reason": "入口脚本改写地址和正文均可从静态HTML复现"},
    },
}


def normalize_layout(text: str) -> str:
    """确定性清理富文本编辑器产生的中文排版空白。"""
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：])\s*", r"\1", value)


def discover_content_url(main_html: str, final_url: str) -> str:
    """优先提取入口脚本对当前概况栏目的真实href赋值。"""
    rewrite = re.search(
        r'''jQuery\(\s*["']#xxgk_215\s+a["']\s*\)\.attr\(\s*["']href["']\s*,\s*["']([^"']+)''',
        main_html,
        flags=re.I,
    )
    if rewrite is not None:
        return urljoin(final_url, rewrite.group(1).strip())
    soup = BeautifulSoup(main_html, "html.parser")
    current_link = soup.select_one("#xxgk_215 a[href]")
    return urljoin(final_url, str(current_link.get("href", "")).strip()) if current_link else ""


def fetch_content_html(main_html: str, final_url: str) -> str:
    """动态发现实际概况页并通过公共增强请求抓取正文。"""
    content_url = discover_content_url(main_html, final_url)
    if not content_url or content_url == final_url:
        raise RuntimeError("入口页未发现有效的#xxgk_215实际概况地址")

    from crawler_core.fetcher import fetch_html_with_strategy

    return fetch_html_with_strategy(content_url, strategy="requests").html


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按#nsks人物简介段顺序提取姓名和完整现任句。"""
    soup = BeautifulSoup(fetch_content_html(html, final_url), "html.parser")
    region = soup.select_one("#nsks")
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
        evidence = evidence_match.group(0).removeprefix("现任").removesuffix("。")
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "入口脚本动态取得#xxgk_215真实概况地址；#nsks p按DOM顺序提取段首姓名与完整现任句",
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
