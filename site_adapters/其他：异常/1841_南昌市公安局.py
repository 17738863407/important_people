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
    "rule_id": "1841",
    "page_type": "人物列表完整页",
    "structure_group": "nanchang_police_current_institution_overview",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "validated_current_entry_only",
    "collector": "raw_http",
    "parser": "nanchang_police_current_entry_v3",
    "leader_region_selector": "当前入口中明确的领导信息区域（目前不存在）",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "risk_flag": "规则入口当前为机构概况页，只展示部门介绍和机构设置，不含领导信息；禁止硬编码2018年旧领导文章或从站内搜索结果拼接人物",
    "confidence": "failed",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    """仅清理网页排版空白，不替换括号或改写原文。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """只核验当前规则入口；入口没有领导信息时明确失败。"""
    soup = BeautifulSoup(html, "html.parser")
    title = _clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")
    body_text = _clean_text(soup.get_text(" ", strip=True))
    if title != "机构概况 | 南昌市公安局":
        raise RuntimeError(f"当前入口标题异常：{title or '<空>'}")
    if "领导信息" not in body_text and "领导简介" not in body_text:
        raise RuntimeError("当前机构概况入口只展示部门介绍和机构设置，网页中没有领导信息")
    raise RuntimeError("当前入口出现领导相关文字但尚无经过验证的人物结构，停止抽取")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
