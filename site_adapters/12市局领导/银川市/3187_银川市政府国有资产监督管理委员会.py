from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3187", "page_type": "多人物详情合并页", "structure_group": "yinchuan_sasac_profile_paragraphs_v2", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_yinchuan_sasac_profile_paragraphs_v2",
    "leader_region_selector": ".zwxxgk_bd", "name_selector": "叶级人物简介段首姓名", "duty_selector": "同一人物简介段完整现任句", "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".zwxxgk_bd"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": None, "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 0},
    "risk_flag": "页面为领导班子职责调整通知；仅提取简介段完整现任句，不扩写市国资委简称", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}

PROFILE_PATTERN = re.compile(r"^([\u4e00-\u9fff·\s]{2,8})\s*[，,]\s*[男女]\s*[，,].*?(现\s*任\s*[^。]*。)")


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按叶级人物简介段顺序提取姓名及同段完整现任句。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector") or ""))
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        if paragraph.select_one("p") is not None:
            continue
        match = PROFILE_PATTERN.search(_clean_text(paragraph.get_text(" ", strip=True)))
        if match is None:
            continue
        name = "".join(match.group(1).split())
        evidence = _clean_text(match.group(2)).removeprefix("现任").removesuffix("。")
        evidence = re.sub(r"[（(]\s*挂职\s*[）)]", "", evidence).strip(" ，,")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser") or ""), "selector_summary": ".zwxxgk_bd内叶级人物简介p；段首姓名；同段完整现任句"})
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
