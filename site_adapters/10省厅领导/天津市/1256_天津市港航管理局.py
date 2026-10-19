from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1256",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_port_numbered_leader_divisions",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_port_numbered_leader_divisions_v1",
    "leader_region_selector": "#zoom .trs_editor_view",
    "name_selector": "编号段落分工关键词前末尾姓名",
    "duty_selector": "编号段落姓名前职务",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "一、",
        "end_anchor": "",
        "include_selectors": ["#zoom .trs_editor_view p"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "编号段落同时包含职务、姓名和主持/分管职责；仅解析职责关键词前的段首，职责说明不得写入依据",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom .trs_editor_view p",
            "name_selector": "编号段落分工关键词前末尾姓名",
            "duty_selector": "编号段落姓名前职务",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "一、",
                "end_anchor": "",
                "include_selectors": ["#zoom .trs_editor_view p"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML编号段落直接包含领导职务、姓名及分工边界",
        },
    },
}


def _clean_text(value: str) -> str:
    """清理零宽字符、全角空格和排版空白。"""
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def _compact_duty(value: str) -> str:
    """合并中文职务被HTML节点拆分后产生的排版空格。"""
    return re.sub(r"\s+", "", _clean_text(value)).strip("：:，。")


def _split_leader_head(value: str) -> tuple[str, str]:
    """从编号段落的职责关键词前拆出职务和姓名。"""
    text = re.sub(r"^[一二三四五六七八九十]+、", "", _clean_text(value))
    head = _clean_text(re.split(r"分管|，主持|主持", text, maxsplit=1)[0]).strip("，。 ")
    match = re.fullmatch(
        r"(?P<duty>.+(?:书记|局长|成员|巡视员|主任|级))\s*(?P<name>[\u4e00-\u9fff]{2,4})",
        head,
    )
    if not match:
        return "", ""
    return _compact_duty(match.group("duty")), re.sub(r"\s+", "", match.group("name"))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按编号段落DOM顺序解析段首职务和姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for paragraph in soup.select("#zoom .trs_editor_view p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if not re.match(r"^[一二三四五六七八九十]+、", text):
            continue
        duty, name = _split_leader_head(text)
        if not name or not duty or name in seen:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_tianjin_port_numbered_leader_divisions_v1",
                "selector_summary": "#zoom编号段落；主持/分管前职务和末尾姓名",
            }
        )

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
