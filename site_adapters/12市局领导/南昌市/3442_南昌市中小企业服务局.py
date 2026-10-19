from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3442",
    "page_type": "人物列表完整页",
    "structure_group": "nanchang_sme_duty_name_profile_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online",
    "parser": "page_nanchang_sme_duty_name_profile_v2",
    "leader_region_selector": ".xxgk-container",
    "name_selector": ".xxgk-container p中性别字段前的职务姓名行",
    "duty_selector": "同一人物简介段中姓名之前的原始职务",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "正文职务文字存在编辑器排版空格，只允许确定性清理排版空白",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".xxgk-container", "row_selector": ".xxgk-container p"},
        "api": {"enabled": False, "reason": "当前HTTPS正文直接包含按版面顺序排列的职务、姓名和性别字段"},
    },
}


def normalize_layout(text: str) -> str:
    """确定性清理富文本编辑器产生的中文字符间排版空白。"""
    value = re.sub(r"[\s\u00a0\u3000]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：])\s*", r"\1", value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序解析“原始职务＋姓名，性别”人物行。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select(".xxgk-container p"):
        text = normalize_layout(paragraph.get_text(" ", strip=True))
        match = re.match(
            r"^(?P<duty>党组成员、副局长|党组书记|副局长|二级调研员|三级调研员)"
            r"(?P<name>[\u4e00-\u9fff·]{2,8})，(?:男|女)，",
            text,
        )
        if match is None:
            continue
        name = match.group("name")
        evidence = match.group("duty")
        if name in seen or not evidence:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".xxgk-container p按DOM顺序；匹配性别字段前的职务姓名行；姓名之前为经排版空白清理的原始职务",
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
