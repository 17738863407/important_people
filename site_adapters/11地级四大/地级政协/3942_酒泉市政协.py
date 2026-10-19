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
    "rule_id": "3942",
    "domain": "zx.jiuquan.gov.cn",
    "page_type": "图片与职务姓名相邻段落",
    "structure_group": "jiuquan_cppcc_article_leaders_2026",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_jiuquan_cppcc_article_leaders_v1",
    "leader_region_selector": "#UCAP-CONTENT",
    "name_selector": "p",
    "duty_selector": "p",
    "detail_link_selector": "",
    "content_scope": {"include_selectors": ["#UCAP-CONTENT"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物图片与职务姓名分置相邻段落，正文含图片和空段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": "#UCAP-CONTENT", "item_selector": ":scope > p"},
        "api": {"enabled": False, "reason": "静态正文已按顺序明确写出完整职务和姓名"},
    },
}


def normalize_text(value: str) -> str:
    """删除段落中的排版空白和特殊空格。"""
    return re.sub(r"[\s\u00a0\u2002\u2003\u3000]+", "", value or "").strip("。；; ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序解析以职务关键词分隔的职务和姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#UCAP-CONTENT")
    if region is None:
        raise RuntimeError("未找到政协领导文章正文 #UCAP-CONTENT")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(r"^(?P<duty>.+?(?:副主席|主席|秘书长))(?P<name>[\u4e00-\u9fff·]{2,4})$")
    for paragraph in region.find_all("p"):
        text = normalize_text(paragraph.get_text(" ", strip=True))
        match = pattern.fullmatch(text)
        if match is None:
            continue
        name = match.group("name")
        duty = match.group("duty")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "#UCAP-CONTENT正文p；主席/副主席/秘书长关键词为职务姓名边界",
            }
        )
    if not rows:
        raise RuntimeError("政协领导正文未解析出有效职务姓名段落")
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
