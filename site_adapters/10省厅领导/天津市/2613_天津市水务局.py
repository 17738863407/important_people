from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2613",
    "page_type": "人物目录详情页",
    "structure_group": "tianjin_water_directory_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_tianjin_water_directory_details_v1",
    "leader_region_selector": "div.zfxxgk.main",
    "name_selector": "目录ldzc人物文章a；详情正文开头姓名",
    "duty_selector": "详情正文姓名后的首个句子",
    "detail_link_selector": "目录ldzc人物文章a[href]",
    "content_scope": {"start_anchor": "领导信息", "end_anchor": "", "include_selectors": ["div.zfxxgk.main"], "exclude_selectors": []},
    "detail_strategy": {
        "required": True,
        "mode": "directory_details",
        "detail_collector_type": "static_http",
        "detail_link_selector": "目录ldzc人物文章a[href]",
        "detail_name_selector": ".trs_editor_view或.view.TRS_UEDITOR正文开头",
        "detail_duty_selector": "正文姓名后的首个句子",
        "detail_content_selector": ".trs_editor_view, .view.TRS_UEDITOR",
        "max_detail_links": 50,
    },
    "risk_flag": "详情存在新旧两种编辑器容器；仅取正文开头姓名后的首个职务句，后续简历和主持/负责/分管不得混入",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.zfxxgk.main",
            "name_selector": "目录ldzc人物文章a",
            "duty_selector": ".trs_editor_view或.view.TRS_UEDITOR正文首句",
            "detail_link_selector": "目录ldzc人物文章a[href]",
            "content_scope": {"start_anchor": "人物姓名", "end_anchor": "首个句号", "include_selectors": [".trs_editor_view", ".view.TRS_UEDITOR"], "exclude_selectors": []},
        },
        "api": {"enabled": False, "reason": "当前静态HTML目录提供人物链接，详情正文开头直接包含姓名和职务句"},
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    text = " ".join(text.split())
    return re.sub(r"\s+([，。；、])", r"\1", text)


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value))


def _fetch_detail(url: str) -> tuple[str, str]:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _extract_duty(html: str, expected_name: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".trs_editor_view") or soup.select_one(".view.TRS_UEDITOR")
    text = _clean_text(scope.get_text(" ", strip=True)) if scope else ""
    match = re.match(rf"{re.escape(expected_name)}\s+(?P<duty>[^。]+。)", text)
    return _clean_text(match.group("duty")).rstrip("。") if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录DOM顺序在线解析新旧详情正文首个职务句。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("div.zfxxgk.main a[href]"):
        name = _clean_name(link.get_text(" ", strip=True))
        detail_url = urljoin(base_url, str(link.get("href", "")))
        if (not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name)
                or not re.search(r"/ldzc/\d{6}/t\d+_\d+\.html", detail_url) or name in seen):
            continue
        detail_html, resolved_url = _fetch_detail(detail_url)
        duty = _extract_duty(detail_html, name)
        if not duty:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": resolved_url, "evidence": duty,
                     "parser": "custom_tianjin_water_directory_details_v1",
                     "selector_summary": "目录ldzc文章；详情新旧编辑器正文姓名后首句"})
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
