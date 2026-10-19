from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1310",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".content",
    "row_selector": ".content li .leader",
    "name_selector": ".leader h2 span",
    "duty_selector": ".leader p中的完整现任句",
    "detail_link_selector": "",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "content内同时含机构导航li；仅解析含.leader的当前人物卡片，并在每卡简介内提取完整现任句。",
}


def normalize_text(text: str) -> str:
    """仅压缩简介中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def normalize_name(text: str) -> str:
    """去除姓名中的排版空格。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(text or "")).strip()


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按人物卡片顺序从当前简介区域提取完整“现任……”句。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for card in soup.select(".content li .leader"):
        name_node = card.select_one("h2 span")
        profile_node = card.select_one("p")
        if name_node is None or profile_node is None:
            continue
        name = normalize_name(name_node.get_text(" ", strip=True))
        profile_text = normalize_text(profile_node.get_text(" ", strip=True))
        match = re.search(r"现任[^。]*。", profile_text)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or match is None:
            continue
        evidence = match.group(0).removeprefix("现任").removesuffix("。")

        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "evidence": evidence,
            }
        )

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
