from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "2409",
    "page_type": "人物列表完整页",
    "structure_group": "xining_ecology_trs_strong_name_duty_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_xining_ecology_trs_strong_name_duty_v2",
    "leader_region_selector": ".view.TRS_UEDITOR.trs_word",
    "name_selector": "p > strong中的首个姓名字段",
    "duty_selector": "p > strong中姓名后的原始职务",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".view.TRS_UEDITOR.trs_word"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": None,
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "online会误跟随页面认证脚本进入OAuth错误页，需保留入口原始HTML；同一加粗节点包含姓名和职务",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _is_hidden(node: Tag) -> bool:
    """排除当前节点或祖先上明确隐藏的段落。"""
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


def _split_name_duty(value: str) -> tuple[str, str]:
    """按网页排版空格拆分姓名和原始职务，不补写语义。"""
    parts = re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip().split(" ")
    if len(parts) < 2:
        return "", ""
    if len(parts[0]) == 1 and len(parts) >= 3 and len(parts[1]) == 1:
        return parts[0] + parts[1], "".join(parts[2:])
    return parts[0], "".join(parts[1:])


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文中加粗人物行的DOM顺序提取姓名与职务。"""
    del final_url
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector") or ""))
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p:has(strong)"):
        if _is_hidden(paragraph):
            continue
        strong = paragraph.select_one("strong")
        name, duty = _split_name_duty(strong.get_text(" ", strip=True) if strong else "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser") or ""),
                "selector_summary": ".view.TRS_UEDITOR.trs_word内p>strong；姓名后文本=原始职务",
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
