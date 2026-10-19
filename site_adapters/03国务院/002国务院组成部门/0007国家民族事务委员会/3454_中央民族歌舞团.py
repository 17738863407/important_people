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
    "rule_id": "3454", "page_type": "多人物详情合并页", "structure_group": "central_ethnic_song_dance_leader_text_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "merged_detail_page", "collector": "static_http", "parser": "page_inline_central_ethnic_song_dance_leader_text_v1",
    "leader_region_selector": "body", "name_selector": "职务冒号后至性别字段前", "duty_selector": "党委职务冒号前", "detail_link_selector": "",
    "content_scope": {"start_anchor": "党委书记：", "end_anchor": "版权所有", "include_selectors": ["body"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "人物简历连续拼接且页脚有地址备案噪声；按党委职务枚举、冒号和紧随姓名的性别字段定位", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_bounded_leader_biography_text",
    "locator": {"text": {"start_anchor": "党委书记：", "end_anchor": "版权所有", "row_pattern": "党委职务：姓名 性别"}, "api": {"enabled": False, "reason": "原始HTML可见正文直接提供现任领导姓名和党委职务"}, "migration": {"source": "legacy_business_source_and_whole_page_scope_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    text = clean_text(soup.get_text(" ", strip=True))
    start = text.find("党委书记：")
    end = text.find("版权所有", start)
    if start < 0:
        return []
    scoped = text[start:end if end >= 0 else None]
    name_pattern = r"[\u4e00-\u9fff]{2,6}(?:·[\u4e00-\u9fff]{2,6})?"
    row_pattern = re.compile(rf"(党委(?:书记|副书记、团长|委员、副团长|委员、纪委书记))：\s*({name_pattern})\s+(?=男|女)")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for duty, name in row_pattern.findall(scoped):
        if name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=leader_text_to_copyright；boundary=gender_field；order=text"})
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
