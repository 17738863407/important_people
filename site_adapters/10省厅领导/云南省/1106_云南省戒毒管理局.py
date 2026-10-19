from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1106",
    "page_type": "人物段落页",
    "structure_group": "yunnan_drug_rehab_static_leader_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "custom_yunnan_drug_rehab_static_leader_paragraphs_v2",
    "leader_region_selector": ".lzy-scroll-wrap p",
    "name_selector": "每段三组NBSP分隔符前",
    "duty_selector": "三组NBSP分隔符后至主持/协助/分管前",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "附件下载",
        "include_selectors": [".lzy-scroll-wrap p"],
        "exclude_selectors": ["主持分工", "协助分工", "分管处室", "隐藏节点"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "raw_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "领导信息直接位于原始HTML段落；姓名内部可能含单个NBSP，姓名与职务以连续三组NBSP为边界",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".lzy-scroll-wrap p",
            "name_selector": "连续三组NBSP分隔符前并清理姓名内部空格",
            "duty_selector": "分隔符后至主持/协助/分管前",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "渲染后首个领导段",
                "end_anchor": "渲染后末个领导段",
                "include_selectors": ["table.tablegkdetail4.tableother4 p"],
                "exclude_selectors": ["主持分工", "协助分工", "分管处室", "隐藏节点"],
            },
        },
        "api": {"enabled": False, "reason": "当前原始HTML已直接包含稳定人物段落，无需额外接口或浏览器渲染"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def _split_paragraph(raw_text: str) -> tuple[str, str]:
    parts = re.split(r"(?:\xa0\s*){3,}", raw_text, maxsplit=1)
    if len(parts) != 2:
        return "", ""
    name = re.sub(r"\s+", "", _clean_text(parts[0]))
    remainder = _clean_text(parts[1]).rstrip("。；;")
    duty = re.split(r"，(?:主持|协助|分管)", remainder, maxsplit=1)[0].strip()
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select(".lzy-scroll-wrap p"):
        if _is_hidden(paragraph):
            continue
        name, duty = _split_paragraph(paragraph.get_text("", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_yunnan_drug_rehab_static_leader_paragraphs_v2",
                "selector_summary": "领导信息段落p；三组NBSP前姓名；主持/协助/分管前职务",
            }
        )
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
