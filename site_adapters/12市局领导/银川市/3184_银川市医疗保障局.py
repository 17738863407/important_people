from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "3184",
    "page_type": "多人物详情合并页",
    "structure_group": "yinchuan_healthcare_leadership_article_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "parse_page",
    "leader_region_selector": ".view.TRS_UEDITOR > p",
    "name_selector": "人物简介段开头姓名及性别",
    "duty_selector": "当前人物简介段内现任片段，按职责起始短语截断",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".view.TRS_UEDITOR"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "requests",
        "detail_link_selector": None,
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "官网当前领导信息合并页；现任片段需在主持、负责、分管等职责短语前截断",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _clean_text(text: str) -> str:
    text = (text or "").replace("\xa0", " ").replace("\u3000", " ")
    text = " ".join(text.split())
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return re.sub(r"\s+([，。；：、！？])", r"\1", text)


def _is_hidden(node: Tag) -> bool:
    """排除当前节点或祖先明确隐藏的人物段。"""
    for current in [node, *node.parents]:
        if not isinstance(current, Tag):
            continue
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if (
            current.has_attr("hidden")
            or str(current.get("aria-hidden", "")).lower() == "true"
            or "display:none" in style
            or "visibility:hidden" in style
            or classes.intersection({"hidden", "hide"})
        ):
            return True
    return False


def _extract_name(text: str) -> str:
    match = re.match(r"^([\u4e00-\u9fff·\s]{2,10}?)[，,]\s*[男女]", text)
    return re.sub(r"\s+", "", match.group(1)) if match else ""


def _extract_evidence(text: str) -> str:
    current_match = re.search(r"现任.+", text)
    if not current_match:
        return ""
    evidence = re.split(
        r"[，,；;。]\s*(?=主持|协助|负责|分管|联系)",
        current_match.group(0),
        maxsplit=1,
    )[0]
    return _clean_text(evidence).removeprefix("现任").strip().rstrip("，,；;。").replace("（挂职）", "").replace("(挂职)", "")


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按正文人物简介段顺序提取姓名与当前职务原文。"""
    del base_url
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for paragraph in soup.select(".view.TRS_UEDITOR > p"):
        if _is_hidden(paragraph):
            continue
        text = _clean_text(paragraph.get_text(" ", strip=True))
        name = _extract_name(text)
        if not name or name in seen:
            continue
        evidence = _extract_evidence(text)
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": rule["parser"],
                "selector_summary": (
                    "strategy=css；leader=.view.TRS_UEDITOR > p；"
                    "name=人物简介段开头姓名及性别；duty=现任片段按职责短语截断；"
                    "detail=共享合并页留空"
                ),
            }
        )
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
