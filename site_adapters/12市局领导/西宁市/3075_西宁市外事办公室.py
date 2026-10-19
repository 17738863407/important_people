from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "3075",
    "page_type": "人物列表完整页",
    "structure_group": "xining_foreign_affairs_function_leaders_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_xining_foreign_affairs_function_leaders_v2",
    "leader_region_selector": "#wenzhangzhengwen",
    "name_selector": "机构职能标题后人物段落冒号前文本",
    "duty_selector": "机构职能标题后人物段落冒号后文本",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "机构职能:",
        "end_anchor": "",
        "include_selectors": ["#wenzhangzhengwen"],
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
    "risk_flag": "正文在机构职能标题前含负责人姓名、联系方式等字段；仅提取标题后的姓名:职务段落",
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
    """仅清理网页排版空白与冒号两侧空白。"""
    value = re.sub(r"[\s\u3000\xa0]+", " ", text or "").strip()
    return re.sub(r"\s*([:：])\s*", r"\1", value)


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
    """按“机构职能”标题后的人物段落顺序提取姓名与原始职务。"""
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
        if text in {"机构职能:", "机构职能："}:
            in_leader_section = True
            continue
        if not in_leader_section or not text:
            continue
        match = re.fullmatch(r"([\u3400-\u9fff·\s]{2,10})[:：](.+)", text)
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group(1))
        duty = _clean_text(match.group(2))
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
                "selector_summary": "#wenzhangzhengwen内机构职能标题后p；冒号前=姓名；冒号后=依据",
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
