from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0715",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "leader_region_selector": "#zoomcon",
    "person_selector": "strong",
    "risk_flag": "online模式会误跟随搜索脚本跳转，raw_http可稳定取得权威正文；页面无人物详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


DUTY_START_PATTERN = (
    r"党组|局长|副局长|一级调研员|市编研中心主任|总工程师|总规划师|总经济师"
)


def clean_text(value: object) -> str:
    """压缩正文排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def clean_name(value: object) -> str:
    """清除姓名中的排版空白，不做语义补全。"""
    return re.sub(r"\s+", "", str(value or "")).strip()


def split_name_duty(value: object) -> tuple[str, str]:
    """依页面职务起始词边界分离姓名与原始职务。"""
    text = clean_text(value)
    match = re.fullmatch(
        rf"(?P<name>[\u3400-\u9fff\s]{{2,10}}?)\s+"
        rf"(?P<duty>(?:{DUTY_START_PATTERN}).*)",
        text,
    )
    if not match:
        return "", ""
    return clean_name(match.group("name")), clean_text(match.group("duty"))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按领导之窗正文顺序提取加粗的姓名职务行。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if not region:
        raise RuntimeError("未找到领导之窗正文")

    rows: list[dict] = []
    seen_names: set[str] = set()
    for node in region.select(page_rule["person_selector"]):
        name, duty = split_name_duty(node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
                "parser": "page_inline_guangzhou_resources_planning_strong_v2",
                "selector_summary": "region=#zoomcon；person=strong姓名+职务；detail=none",
            }
        )

    if not rows:
        raise RuntimeError("领导之窗正文未提取到有效人物")
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
