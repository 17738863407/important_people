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
    "rule_id": "2400",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_commerce_labeled_blocks",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_commerce_labeled_blocks_v1",
    "leader_region_selector": "#zoom.xw-txt",
    "name_selector": "姓名标签及其下一行",
    "duty_selector": "职务标签至分工标签之间",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "姓名：",
        "end_anchor": "附件：",
        "include_selectors": ["#zoom.xw-txt"],
        "exclude_selectors": ["分工字段"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "姓名与职务均可能在标签后换行，职务还可能跨多个文本行；以姓名/职务/分工标签状态机解析，分工不得并入依据",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom.xw-txt",
            "name_selector": "姓名标签及其下一行",
            "duty_selector": "职务标签至分工标签之间",
            "detail_link_selector": "",
            "content_scope": {"start_anchor": "姓名：", "end_anchor": "附件：", "include_selectors": ["#zoom.xw-txt"], "exclude_selectors": ["分工字段"]},
        },
        "api": {"enabled": False, "reason": "当前静态HTML正文直接包含7组姓名、职务和分工标签"},
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文标签状态机解析单行及跨行姓名、职务。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one("#zoom.xw-txt")
    if scope is None:
        return []
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    current_name = ""
    duty_parts: list[str] = []
    reading_duty = False
    pending_name = False

    def flush() -> None:
        nonlocal current_name, duty_parts, reading_duty, pending_name
        name = _clean_name(current_name)
        duty = _clean_text("".join(duty_parts))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) and duty and name not in seen:
            seen.add(name)
            records.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty,
                            "parser": "custom_tianjin_commerce_labeled_blocks_v1",
                            "selector_summary": "#zoom正文姓名/职务/分工标签状态机"})
        current_name, duty_parts, reading_duty, pending_name = "", [], False, False

    for raw_line in scope.get_text("\n", strip=True).splitlines():
        line = _clean_text(raw_line)
        if not line or line == "无障碍语音播报" or line.startswith("0:00"):
            continue
        if line.startswith("姓名："):
            flush()
            current_name = line.removeprefix("姓名：")
            pending_name = not bool(current_name)
        elif pending_name:
            current_name, pending_name = line, False
        elif line.startswith("职务："):
            reading_duty = True
            value = line.removeprefix("职务：")
            if value:
                duty_parts.append(value)
        elif line.startswith("分工："):
            reading_duty = False
        elif line.startswith("附件：") or line.startswith("分享到："):
            break
        elif reading_duty:
            duty_parts.append(line)
    flush()
    return records


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
