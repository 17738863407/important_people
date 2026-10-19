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
    "rule_id": "1553",
    "page_type": "人物列表完整页",
    "structure_group": "应急管理部驻部纪检组姓名职务相邻段落",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MemDisciplineLeaderAdjacentParagraphParser_v1",
    "leader_region_selector": ".pages_content .TRS_Editor",
    "name_selector": "p:has(b)",
    "duty_selector": "姓名段的下一非空p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文含打印控件与页面元数据；仅按TRS正文内加粗姓名段及其下一职务段配对，括号空格仅作排版清理",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按姓名加粗段与下一非空职务段配对，继承页面顺序。"""
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.select(".pages_content .TRS_Editor p")
    if not paragraphs:
        raise RuntimeError("未找到驻部纪检监察组领导正文段落")
    records: list[dict] = []
    seen_names: set[str] = set()
    for index, paragraph in enumerate(paragraphs):
        bold = paragraph.find("b")
        if bold is None:
            continue
        name = _clean_text(paragraph.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen_names:
            continue
        duty = ""
        for next_paragraph in paragraphs[index + 1 :]:
            duty = _clean_text(next_paragraph.get_text(" ", strip=True))
            if duty:
                break
        if not duty or next_paragraph.find("b") is not None:
            raise RuntimeError(f"未找到{name}对应的相邻职务段")
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".pages_content .TRS_Editor p；加粗姓名段与下一非空职务段",
            }
        )
    if not records:
        raise RuntimeError("领导正文未解析到人物记录")
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
