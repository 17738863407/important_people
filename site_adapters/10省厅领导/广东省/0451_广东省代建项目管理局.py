from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0451",
    "page_type": "人物列表完整页",
    "structure_group": "gd_djj_article_strong_name_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "online_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".article-content",
    "name_selector": ".article-content p > strong",
    "duty_selector": ".article-content p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文相邻段含分工信息，仅接受strong姓名所在同一段的职务文本",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _compact(text: str) -> str:
    """清理网页排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u3000\xa0]+", "", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从领导简介正文中提取strong姓名与同段原始职务。"""
    from bs4 import BeautifulSoup

    del final_url, page_rule
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for para in soup.select(".article-content p"):
        strong = para.find("strong", recursive=False)
        if strong is None:
            continue
        name = _compact(strong.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or name in seen:
            continue
        full_text = _compact(para.get_text(" ", strip=True))
        if not full_text.startswith(name):
            continue
        duty = full_text[len(name) :].strip("：:，,、")
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
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
