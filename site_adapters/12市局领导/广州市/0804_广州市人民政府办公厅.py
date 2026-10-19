from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0804",
    "page_type": "人物目录详情页",
    "structure_group": "领导分工正文姓名冒号职务",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "online",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".article-content p",
    "name_selector": "strong",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".article-content"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "职务后紧接较长工作分工，必须在首个逗号处截断",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    """压缩网页排版空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文顺序提取加粗姓名及冒号后的原始职务短语。"""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one(".article-content")
    if article is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in article.select("p"):
        strong = paragraph.select_one("strong")
        if strong is None:
            continue
        name = clean_text(strong.get_text(" ", strip=True)).rstrip("：:").replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
        duty_match = re.search(r"[：:]\s*([^，,。；;]+)", paragraph_text)
        if duty_match is None:
            continue
        duty = clean_text(duty_match.group(1))
        if not re.search(r"市长|秘书长", duty) or name in seen:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": ".article-content p内strong姓名及冒号后首个职务短语",
            }
        )
        seen.add(name)

    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
