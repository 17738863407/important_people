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
    "rule_id": "3943",
    "domain": "www.zxlf.gov.cn",
    "page_type": "富文本职务分组名单",
    "structure_group": "langfang_cppcc_article_grouped_names_2021",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_langfang_cppcc_grouped_names_v1",
    "leader_region_selector": ".art_dd",
    "name_selector": "p span",
    "duty_selector": "p span",
    "detail_link_selector": "",
    "content_scope": {"include_selectors": [".art_dd"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同一文章还列出58名常务委员，领导抽取必须在常务委员标题前终止",
    "confidence": "medium",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".art_dd", "segment_selector": "p span"},
        "api": {"enabled": False, "reason": "静态富文本正文已明确给出职务标题和姓名分组"},
    },
}


def compact_text(value: str) -> str:
    """清除富文本片段中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按span边界解析主席、副主席、秘书长，并在常务委员前停止。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".art_dd")
    if region is None:
        raise RuntimeError("未找到政协领导文章正文 .art_dd")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    current_duty = ""

    def add_name(raw_name: str) -> None:
        name = re.sub(r"（[^）]*）", "", compact_text(raw_name)).strip("：:；;。")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or name in seen or not current_duty:
            return
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": current_duty,
                "evidence": current_duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".art_dd富文本span分组；遇常务委员标题终止",
            }
        )

    for paragraph in region.find_all("p"):
        if paragraph.find("p") is not None:
            continue
        paragraph_text = compact_text(paragraph.get_text(" ", strip=True))
        if paragraph_text.startswith("常务委员："):
            break
        if not any(label in paragraph_text for label in ("主席：", "副主席：", "秘书长：")):
            continue
        for span in paragraph.find_all("span"):
            segment = compact_text(span.get_text(" ", strip=True))
            if not segment or re.fullmatch(r"（[^）]*）", segment):
                continue
            parts = re.split(r"(副主席|秘书长|主席)：", segment)
            if len(parts) == 1:
                add_name(segment)
                continue
            if parts[0]:
                add_name(parts[0])
            for index in range(1, len(parts), 2):
                current_duty = parts[index]
                following = parts[index + 1] if index + 1 < len(parts) else ""
                if following:
                    add_name(following)
    if not rows:
        raise RuntimeError("政协领导文章未解析出主席、副主席或秘书长")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
