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
    "rule_id": "1546",
    "page_type": "职务分组名单页",
    "structure_group": "文旅部直属单位现任领导段落组",
    "reuse_scope": "mct_affiliated_unit_article",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MctAffiliatedUnitCurrentLeadersParser_v2",
    "leader_region_selector": "#zoom .TRS_Editor p",
    "name_selector": "现任领导与联系方式标题之间各段冒号后",
    "duty_selector": "现任领导与联系方式标题之间各段冒号前",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "单位简介含党校别名与培训信息；必须以现任领导和联系方式标题限定人物段落，清理排版空格但不改动职务语义",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析“现任领导”至“联系方式”之间的职务姓名段落。"""
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.select("#zoom .TRS_Editor p")
    if not paragraphs:
        raise RuntimeError("未找到中央文化和旅游管理干部学院正文段落")
    in_leader_section = False
    records: list[dict] = []
    seen_names: set[str] = set()
    for paragraph in paragraphs:
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if text == "现任领导":
            in_leader_section = True
            continue
        if in_leader_section and text == "联系方式":
            break
        if not in_leader_section:
            continue
        matched = re.fullmatch(r"(.+?)[：:]([\u4e00-\u9fff·]{2,5})", text)
        if not matched:
            continue
        duty, name = matched.groups()
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "parser": PAGE_RULE["parser"], "selector_summary": "#zoom .TRS_Editor p；现任领导至联系方式标题之间；职务：姓名完整原文"})
    if not records:
        raise RuntimeError("现任领导分组未解析到人物记录")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
