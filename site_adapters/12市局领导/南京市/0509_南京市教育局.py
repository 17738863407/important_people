from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0509",
    "page_type": "人物列表完整页",
    "structure_group": "nanjing_education_leader_intro_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "leader_region_selector": "#nsks .view.TRS_UEDITOR",
    "name_selector": "p:has(strong)",
    "risk_flag": "机构职能与领导信息同页分区展示，只能解析nsks区域中含现任句的人物简介段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    """确定性清理富文本编辑器产生的排版空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*([、，。；：])\s*", r"\1", text)
    return re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按领导信息富文本区域中的人物简介段落顺序提取姓名和现任句。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#nsks .view.TRS_UEDITOR")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    for paragraph in region.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = re.match(
            r"^(?P<name>[\u3400-\u9fff·]{2,4})[，,].*?(?P<evidence>现任[^。]*。)",
            text,
        )
        if match is None:
            continue
        evidence = re.sub(r"^现任\s*", "", match.group("evidence")).rstrip("。")
        rows.append(
            {
                "order": str(len(rows) + 1),
                "name": match.group("name"),
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": "inline_nanjing_education_leader_intro_paragraphs_v1",
            }
        )
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
