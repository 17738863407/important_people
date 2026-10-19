from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3934",
    "domain": "www.zxgy.gov.cn",
    "page_type": "人物图片卡片列表",
    "structure_group": "guangyuan_cppcc_article_cards_2026",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_guangyuan_cppcc_article_cards_v1",
    "leader_region_selector": "a[href^='article.html?id=']",
    "name_selector": "p",
    "duty_selector": "p",
    "detail_link_selector": "a[href^='article.html?id=']",
    "content_scope": {"include_selectors": [], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面缺少稳定人物容器类名，必须以头像卡片链接和受限职务文本双重校验",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "item_selector": "a[href^='article.html?id=']:has(img):has(p)",
            "field_selector": "p",
        },
        "api": {"enabled": False, "reason": "静态HTML人物卡片已含姓名、职务和详情链接"},
    },
}


def normalize_text(value: str) -> str:
    """清除零宽字符及纯排版空白。"""
    return re.sub(r"[\s\u00a0\u200b\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按卡片DOM顺序解析“职务：姓名”及独立人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(r"^(主席|副主席|秘书长)：([\u4e00-\u9fff·]{2,4})$")
    for link in soup.select("a[href^='article.html?id=']"):
        if link.find("img") is None:
            continue
        paragraph = link.find("p")
        text = normalize_text(paragraph.get_text(" ", strip=True) if paragraph else "")
        match = pattern.fullmatch(text)
        if match is None:
            continue
        duty, name = match.groups()
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url or str(page_rule.get("url", "")), str(link.get("href", ""))),
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "article.html人物卡片链接；p字段=职务：姓名",
            }
        )
    if not rows:
        raise RuntimeError("未从政协领导图片卡片中解析出有效人物")
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
