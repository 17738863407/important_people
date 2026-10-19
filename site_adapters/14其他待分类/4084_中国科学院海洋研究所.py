from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4084",
    "page_type": "领导卡片页",
    "structure_group": "qdio_leader_heading_link_card",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_qdio_leader_heading_link_card",
    "leader_region_selector": ".boxstyle",
    "risk_flag": "姓名和职务同在标题链接中，按姓名后首个职务文本切分",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """逐张领导卡片处理标题链接，保留可验证的对应详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".boxstyle"):
        heading = card.select_one(".txtinfo h4 a[href]")
        if heading is None:
            continue
        text = re.sub(r"\s+", "", heading.get_text(" ", strip=True))
        split = next(
            (
                (text[:name_length], text[name_length:])
                for name_length in (2, 3, 4)
                if re.match(r"(?:党委|纪委|副|所长|院长|主任|书记)", text[name_length:])
            ),
            None,
        )
        if split is None:
            continue
        rows.append({
            "name": split[0],
            "duty": split[1],
            "evidence": split[1],
            "detail_url": urljoin(final_url, heading["href"]),
        })
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
