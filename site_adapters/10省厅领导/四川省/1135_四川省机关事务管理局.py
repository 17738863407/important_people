from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1135",
    "domain": "jgswj.sc.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "sichuan_government_affairs_leader_li",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_sichuan_jgj_leader_li_v2",
    "leader_region_selector": ".leader li",
    "duty_end_pattern": r"工作分工[:：]?",
    "name_duty_pattern": r"^(.+?)\s+((?:省政府|局党组|驻局|二级).+)$",
    "detail_strategy": {
        "required": False,
        "mode": "none",
    },
    "risk_flag": "每个人物项同时包含长篇工作分工；只提取工作分工标签之前的姓名和职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def normalize_space(value: str) -> str:
    """压缩页面中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def clean_compact(value: str) -> str:
    """移除姓名内部排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def parse_name_duty(text: str, page_rule: dict) -> tuple[str, str]:
    """从当前人物项的“姓名 职务 工作分工”结构切出字段。"""
    head = re.split(str(page_rule["duty_end_pattern"]), text, maxsplit=1)[0].strip()
    match = re.match(str(page_rule["name_duty_pattern"]), head)
    if not match:
        return "", ""

    name = clean_compact(match.group(1))
    duty = normalize_space(match.group(2)).strip("，,、 ")
    if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
        return "", ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导列表DOM顺序提取姓名和工作分工前的原始职务。"""
    from bs4 import BeautifulSoup

    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(str(page_rule["leader_region_selector"])):
        text = normalize_space(item.get_text(" ", strip=True))
        name, duty = parse_name_duty(text, page_rule)
        if not name or not duty or name in seen:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule["parser"]),
                "selector_summary": ".leader li内工作分工标签之前的姓名和职务",
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
