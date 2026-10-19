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
    "rule_id": "0700",
    "domain": "www.gdzl.agri.cn",
    "page_type": "人物列表完整页",
    "structure_group": "gdzl_leader_duty_name_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_gdzl_center_leaders_v1",
    "leader_region_selector": ".cont_text .Custom_UnionStyle",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "中心领导", "end_anchor": "", "include_selectors": [".cont_text .Custom_UnionStyle"], "exclude_selectors": []},
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
        "candidate_links": [],
    },
    "risk_flag": "二字姓名可被跨标签及EM空格拆分，必须仅在同一人物段落内合并",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".cont_text .Custom_UnionStyle",
            "name_selector": "",
            "duty_selector": "",
            "detail_link_selector": "",
            "content_scope": {"start_anchor": "中心领导", "end_anchor": "", "include_selectors": [".cont_text .Custom_UnionStyle"], "exclude_selectors": []},
        },
        "api": {"enabled": False, "reason": "当前HTTP响应已直接提供中心领导职务姓名段落"},
        "migration": {"source": "legacy_page_rule", "verified_status": "verified_online", "behavior_changed": True},
    },
}


def compact_text(value: str) -> str:
    """删除同一人物段落中的确定性排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2002\u2003\u2004\u2005\u2006]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导正文段落原始顺序解析“职务：姓名”。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = "strategy=custom_parse_page；leader=.cont_text .Custom_UnionStyle；item=p；pattern=职务：姓名"

    for paragraph in soup.select(".cont_text .Custom_UnionStyle p"):
        text = compact_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(主任|总农艺师|副主任)[：:]([\u4e00-\u9fff·]{2,5})", text)
        if not match:
            continue
        duty, name = match.groups()
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": selector_summary,
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
