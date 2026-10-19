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
    "rule_id": "3933",
    "domain": "www.fsszx.gov.cn",
    "page_type": "职务标题多人名单",
    "structure_group": "fushun_cppcc_newscontent_grouped_names_2026",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_fushun_cppcc_grouped_names_v1",
    "leader_region_selector": "#NewsType .NewsContent",
    "name_selector": "p",
    "duty_selector": "p strong",
    "detail_link_selector": "",
    "content_scope": {
        "include_selectors": ["#NewsType .NewsContent"],
        "exclude_selectors": ["script", "style"],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "副主席名单跨段落，必须继承最近职务标题且不得扫描文章外导航",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#NewsType .NewsContent",
            "item_selector": ":scope > p",
            "duty_label_selector": "strong",
        },
        "api": {"enabled": False, "reason": "当前静态文章正文已明确列出职务标题和姓名"},
    },
}


def compact_text(value: str) -> str:
    """删除名单中的排版空白和不间断空格。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序解析职务标题及其连续姓名名单。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#NewsType .NewsContent")
    if region is None:
        raise RuntimeError("未找到政协领导名单正文 #NewsType .NewsContent")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    current_duty = ""
    for paragraph in region.find_all("p", recursive=False):
        strong = paragraph.find("strong")
        if strong is not None:
            label = compact_text(strong.get_text(" ", strip=True)).strip("：:；;。")
            if label in {"主席", "副主席", "秘书长", "副秘书长"}:
                current_duty = label
            strong.extract()
        text = paragraph.get_text(" ", strip=True)
        if not current_duty or not compact_text(text):
            continue
        for match in re.finditer(r"[\u4e00-\u9fff·]{2,4}(?:（[男女]）)?", text):
            name = re.sub(r"（[男女]）$", "", compact_text(match.group(0)))
            if name in seen:
                continue
            seen.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": current_duty,
                    "evidence": current_duty,
                    "detail_url": "",
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": "#NewsType .NewsContent直属p；strong职务标题 + 连续姓名段落",
                }
            )
    if not rows:
        raise RuntimeError("政协领导名单正文未解析出有效职务分组和姓名")
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
