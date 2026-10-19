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
    "rule_id": "3949",
    "domain": "www.njszx.gov.cn",
    "page_type": "领导分工正文",
    "structure_group": "neijiang_cppcc_work_division_article",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_neijiang_cppcc_division_v1",
    "leader_region_selector": ".detail",
    "name_selector": ".detail p",
    "duty_selector": ".detail p",
    "content_scope": {"include_selectors": [".detail"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名职务段落与主持、分管职责段落交替出现，必须排除独立职责段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".detail", "record_selector": "p"},
        "text_pattern": "^(主席|副主席|秘书长)(中文姓名)$",
        "api": {"enabled": False, "reason": "静态文章正文已直接包含当前职务姓名段落"},
    },
}


def normalize_text(value: str) -> str:
    """删除全角、半角和特殊排版空格。"""
    return re.sub(r"[\s\u00a0\u2002\u2003\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从交替段落中仅保留明确的职务姓名记录。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".detail")
    if region is None:
        raise RuntimeError("未找到领导分工正文 .detail")
    rows: list[dict[str, str]] = []
    pattern = re.compile(r"^(主席|副主席|秘书长)([\u3400-\u9fff·]{2,4})$")
    for paragraph in region.select("p"):
        text = normalize_text(paragraph.get_text(" ", strip=True))
        match = pattern.fullmatch(text)
        if not match:
            continue
        duty, name = match.groups()
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".detail正文中严格匹配职务加中文姓名的段落",
            }
        )
    if not rows:
        raise RuntimeError("领导分工正文未解析出有效职务姓名记录")
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
