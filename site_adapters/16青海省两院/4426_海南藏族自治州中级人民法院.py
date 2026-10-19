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


def normalize_field_text(text: str) -> str:
    """清除正文编辑器引入的排版空白，不改写字段语义。"""
    value = str(text or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按正文中重复出现的“姓名—现任职务”字段对提取领导。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".detail > .text")
    if region is None:
        raise RuntimeError("页面未找到领导正文区域 .detail > .text")

    rows: list[dict[str, str]] = []
    pending_name = ""
    for paragraph in region.select("p"):
        text = normalize_field_text(paragraph.get_text(" ", strip=True))
        if text.startswith("姓名："):
            if pending_name:
                raise RuntimeError(f"姓名字段缺少对应现任职务：{pending_name}")
            name = text.removeprefix("姓名：").strip()
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                raise RuntimeError(f"姓名字段格式异常：{text}")
            pending_name = name
            continue
        if text.startswith("现任职务：") and pending_name:
            duty = text.removeprefix("现任职务：").strip("。；; ")
            if not duty:
                raise RuntimeError(f"现任职务字段为空：{pending_name}")
            rows.append(
                {
                    "name": pending_name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "confidence": "high",
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": (
                        "strategy=custom_parse_page；region=.detail>.text；"
                        "fields=p文本中的姓名与现任职务；detail=none"
                    ),
                }
            )
            pending_name = ""

    if pending_name:
        raise RuntimeError(f"姓名字段缺少对应现任职务：{pending_name}")
    if not rows:
        raise RuntimeError("领导正文未解析出完整的姓名—现任职务字段对")
    return rows


PAGE_RULE = {
    "rule_id": "4426",
    "domain": "qhhnzy.qhwsfy.gov.cn",
    "page_type": "领导字段对正文页",
    "structure_group": "qinghai_court_name_current_duty_fields",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "page_qinghai_court_name_current_duty_fields_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".detail > .text",
    "name_selector": "p",
    "duty_selector": "p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "人物照片与出生年月等简介字段夹在姓名和现任职务之间，必须按字段边界配对",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator": {
        "css": {
            "leader_region_selector": ".detail > .text",
            "field_selector": "p",
        },
        "api": {"enabled": False, "reason": "姓名与现任职务由当前静态正文明确直出"},
    },
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
