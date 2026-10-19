from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """清理页面数据字段中的排版空白。"""
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析页面内Vue数据数组，保持数组中的人物顺序。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    script_text = next((node.get_text() for node in soup.find_all("script") if "lb:[" in node.get_text()), "")
    marker = re.search(r"\blb\s*:\s*", script_text)
    if marker is None:
        return []
    try:
        items, _ = json.JSONDecoder().raw_decode(script_text[marker.end() :])
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(items, list):
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        name = re.sub(r"\s+", "", str(item.get("title") or ""))
        duty = clean_text(str(item.get("subtitle") or ""))
        person_id = str(item.get("id") or "").strip()
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name)
            or not duty
            or not re.fullmatch(r"\d+", person_id)
            or name in seen
        ):
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, f"/html/xxgkdy/{person_id}.html"),
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_qinghai_defense_vue_data_v2",
                "selector_summary": "Vue lb JSON：title姓名；subtitle职务；id与页面详情模板生成链接",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2184",
    "page_type": "人物列表完整页",
    "structure_group": "qinghai_defense_vue_embedded_data",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "embedded_json",
    "collector": "static_http",
    "parser": "page_inline_qinghai_defense_vue_data_v2",
    "leader_region_selector": "#vue2",
    "name_selector": "Vue lb[].title",
    "duty_selector": "Vue lb[].subtitle",
    "detail_link_selector": "Vue模板/html/xxgkdy/{id}.html",
    "content_scope": {
        "start_anchor": "领导简介",
        "end_anchor": "",
        "include_selectors": ["#vue2"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "Vue模板/html/xxgkdy/{id}.html",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "站点标题仍显示历史名称青海省人民防空办公室",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "embedded_json",
    "locator": {
        "css": {
            "leader_region_selector": "#vue2",
            "name_selector": "Vue lb[].title",
            "duty_selector": "Vue lb[].subtitle",
            "detail_link_selector": "Vue模板/html/xxgkdy/{id}.html",
            "content_scope": {
                "start_anchor": "领导简介",
                "end_anchor": "",
                "include_selectors": ["#vue2"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "当前HTML已嵌入完整Vue人物JSON数组"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online_embedded_json",
            "behavior_changed": True,
        },
    },
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
