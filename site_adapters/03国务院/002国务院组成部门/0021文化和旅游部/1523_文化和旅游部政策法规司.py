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
    "rule_id": "1523",
    "page_type": "人物列表完整页",
    "structure_group": "文旅部机关正文首部领导段落",
    "reuse_scope": "mct_department_article",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MctDepartmentArticleParagraphLeadersParser_v2",
    "leader_region_selector": "#zoom .TRS_Editor p",
    "name_selector": "主要职责标题前各段冒号后",
    "duty_selector": "主要职责标题前各段冒号前",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文后续含主要职责、组织机构表格和大量页面模板文本；必须限定#zoom正文段落并在主要职责标题处停止。页面iframe仅为页脚",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析正文主要职责标题之前的“职务：姓名”段落。"""
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.select("#zoom .TRS_Editor p")
    if not paragraphs:
        raise RuntimeError("未找到政策法规司正文段落")
    records: list[dict] = []
    seen_names: set[str] = set()
    for paragraph in paragraphs:
        evidence = _clean_text(paragraph.get_text(" ", strip=True))
        if evidence.startswith("主要职责"):
            break
        matched = re.fullmatch(r"(.+?)[：:]([\u4e00-\u9fff·]{2,5})", evidence)
        if not matched:
            continue
        duty, name = matched.groups()
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "#zoom .TRS_Editor p；主要职责标题前；职务：姓名完整原文",
            }
        )
    if not records:
        raise RuntimeError("政策法规司正文首部未解析到领导记录")
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
