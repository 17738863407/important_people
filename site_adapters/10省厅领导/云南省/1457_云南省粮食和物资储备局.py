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
    "rule_id": "1457",
    "page_type": "人物列表完整页",
    "structure_group": "yunnan_grain_duty_name_headings",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_yunnan_grain_duty_name_headings_v1",
    "leader_region_selector": ".lzy-scroll-wrap p strong",
    "name_selector": ".lzy-scroll-wrap p strong末个空白分词",
    "duty_selector": ".lzy-scroll-wrap p strong姓名前文本",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导信息首个加粗标题",
        "end_anchor": "领导信息末个加粗标题",
        "include_selectors": [".lzy-scroll-wrap p strong"],
        "exclude_selectors": ["左侧导航", "附件下载", "友情链接", "页脚"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "加粗标题结构为职务+空白+姓名；不依赖固定职务关键词，页面没有人物独立链接",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".lzy-scroll-wrap p strong",
            "name_selector": "末个空白分词",
            "duty_selector": "姓名前全部文本",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "领导信息首个加粗标题",
                "end_anchor": "领导信息末个加粗标题",
                "include_selectors": [".lzy-scroll-wrap p strong"],
                "exclude_selectors": ["左侧导航", "附件下载", "友情链接", "页脚"],
            },
        },
        "api": {"enabled": False, "reason": "当前静态HTML加粗标题直接提供职务和姓名，页面无人物详情链接"},
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
        if "lzy-scroll-wrap" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for heading in soup.select(".lzy-scroll-wrap p strong"):
        if _is_hidden(heading):
            continue
        parts = _clean_text(heading.get_text(" ", strip=True)).split(" ")
        if len(parts) < 2:
            continue
        name = re.sub(r"\s+", "", parts[-1])
        duty = " ".join(parts[:-1]).strip(" ：:，,。.")
        if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_yunnan_grain_duty_name_headings_v1",
                "selector_summary": ".lzy-scroll-wrap p strong；末词姓名；前文职务",
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
