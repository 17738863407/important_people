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
    "rule_id": "4340",
    "page_type": "党委名单文章页",
    "structure_group": "fmuseum_party_leader_lines_v1",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_fmuseum_leaders_v1",
    "leader_region_selector": "article, .max-w-screen-lg",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "仅抽取正文中‘姓名：中国财税博物馆职务’段落。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "organization_prefixed_lines",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按文章段落顺序提取馆党委成员。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for paragraph in soup.select("p"):
        text = " ".join(paragraph.get_text(" ", strip=True).replace("\u3000", " ").split())
        matched = re.fullmatch(r"([\u3400-\u9fff· ]{2,10})[：:]\s*(中国财税博物馆.+)", text)
        if not matched:
            continue
        name = re.sub(r"\s+", "", matched.group(1))
        if re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
            rows.append({"name": name, "duty": matched.group(2), "detail_url": ""})
    if not rows:
        raise RuntimeError("馆党委文章未解析到机构前缀明确的成员行")
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
