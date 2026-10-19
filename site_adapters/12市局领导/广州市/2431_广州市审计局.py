from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2431",
    "page_type": "人物表格页",
    "structure_group": "个人简介与现任句重复人物块",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "online",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".article-content",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "个人简介",
        "end_anchor": "",
        "include_selectors": [".article-content"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文同时含个人简介和工作分工，必须限于各人物简介块提取现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def normalize_space(value: str) -> str:
    """将网页排版空白压缩为空格，不改变正文语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文顺序解析每个“个人简介”块中的姓名和完整现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one(".article-content")
    if article is None:
        return []

    text = normalize_space(article.get_text(" ", strip=True))
    block_pattern = re.compile(
        r"个人简介\s+(?P<name>[\u4e00-\u9fff·]{2,4})[，,]"
        r"(?P<profile>.*?)"
        r"(?P<evidence>现任[^。]*。)"
        r"(?=\s*工作分工|\s*个人简介|$)"
    )
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for match in block_pattern.finditer(text):
        name = match.group("name")
        if name in seen:
            continue
        evidence = normalize_space(match.group("evidence"))
        cleaned_evidence = evidence.removeprefix("现任").removesuffix("。")
        rows.append(
            {
                "name": name,
                "duty": cleaned_evidence,
                "evidence": cleaned_evidence,
                "detail_url": "",
                "selector_summary": ".article-content内个人简介块的完整现任句",
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
