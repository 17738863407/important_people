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
    "rule_id": "0748", "page_type": "职务分组名单页", "structure_group": "gstikc_leader_colon_rows_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_gstikc_leader_colon_rows_v1",
    "leader_region_selector": ".index-news .zhuren .TRS_Editor p", "name_selector": "colon_suffix", "duty_selector": "colon_prefix", "detail_link_selector": "",
    "content_scope": {"start_anchor": "关于我们", "end_anchor": "Copyright", "include_selectors": [".index-news .zhuren .TRS_Editor"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "姓名和主任标题含em-space排版空格，仅做字符间空格清理并按首个冒号拆分", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_colon_rows",
    "locator": {"css": {"leader_region_selector": ".index-news .zhuren .TRS_Editor p", "row_pattern": "职务：姓名"}, "api": {"enabled": False, "reason": "原始HTML领导正文直接提供职务冒号姓名行"}, "migration": {"source": "legacy_business_source_and_stale_metadata_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def compact_chinese(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select(page_rule["leader_region_selector"]):
        line = paragraph.get_text(" ", strip=True).replace(":", "：", 1)
        if "：" not in line:
            continue
        duty_raw, name_raw = line.split("：", 1)
        duty = compact_chinese(duty_raw)
        name = compact_chinese(name_raw)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=zhuren_TRS_Editor；boundary=first_colon；order=dom"})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
