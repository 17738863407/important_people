from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "3076",
    "page_type": "人物列表完整页",
    "structure_group": "xining_petition_strong_leader_lines_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_xining_petition_strong_leader_lines_v2",
    "leader_region_selector": ".view",
    "name_selector": "领导信息至机构职能之间strong行开头姓名",
    "duty_selector": "同一strong行姓名后的原始职务",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导信息:",
        "end_anchor": "机构职能:",
        "include_selectors": [".view"],
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
    "risk_flag": "领导姓名职务行与负责、分管段落交替出现；只解析领导区间内strong行，不给职务补机构前缀",
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


def _clean_text(text: str) -> str:
    """仅合并网页排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text or "").strip()


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


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导信息区间内加粗姓名职务行的DOM顺序提取。"""
    del final_url
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector") or ""))
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    in_leader_section = False
    for paragraph in region.select("p"):
        if _is_hidden(paragraph):
            continue
        text = _clean_text(paragraph.get_text(" ", strip=True))
        compact = re.sub(r"\s+", "", text)
        if compact in {"领导信息:", "领导信息："}:
            in_leader_section = True
            continue
        if compact in {"机构职能:", "机构职能："}:
            break
        if not in_leader_section:
            continue
        strong = paragraph.select_one("strong")
        if strong is None:
            continue
        strong_text = _clean_text(strong.get_text(" ", strip=True))
        match = re.fullmatch(r"([\u3400-\u9fff]\s*[\u3400-\u9fff]{1,3})\s+(.+)", strong_text)
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group(1))
        duty = _clean_text(match.group(2)).rstrip("。")
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
                "selector_summary": ".view内领导信息至机构职能之间strong行；开头姓名；其后原始职务",
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
