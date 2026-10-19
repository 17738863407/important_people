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
    "rule_id": "2542",
    "page_type": "多人物详情合并页",
    "structure_group": "tianjin_stats_inline_leader_blocks",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_stats_inline_leader_blocks_v1",
    "leader_region_selector": "#ul_db",
    "name_selector": ".zh-ldxx-info .info .con直属div第1项",
    "duty_selector": ".zh-ldxx-info .info .con直属div第2项",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "机构设置",
        "include_selectors": ["#ul_db > .zh-ldxx-info"],
        "exclude_selectors": [".zh-jigoushezhi", "领导分工区域"],
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
    "risk_flag": "领导区后紧邻大量机构设置；人物菜单仅为javascript切换，同块还含简介和分工，仅读取顶部.info .con强字段",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#ul_db > .zh-ldxx-info",
            "name_selector": ".info .con直属div第1项",
            "duty_selector": ".info .con直属div第2项",
            "detail_link_selector": "",
            "content_scope": {"start_anchor": "领导信息", "end_anchor": "机构设置", "include_selectors": ["#ul_db"], "exclude_selectors": ["领导简介区域", "领导分工区域"]},
        },
        "api": {"enabled": False, "reason": "当前静态HTML五个人物块顶部直接提供姓名和职务强字段"},
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按内联人物块DOM顺序读取顶部姓名和职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for block in soup.select("#ul_db > .zh-ldxx-info"):
        fields = block.select(":scope > .info .con > div")
        if len(fields) < 2:
            continue
        name = re.sub(r"\s+", "", _clean_text(fields[0].get_text(" ", strip=True)))
        duty = _clean_text(fields[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": "",
            "evidence": duty,
            "parser": "custom_tianjin_stats_inline_leader_blocks_v1",
            "selector_summary": "#ul_db直属zh-ldxx-info；顶部.info .con前两项姓名/职务",
        })
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
