from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1477",
    "page_type": "人物目录详情页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".scroll_main1 .zfxxgk_zdgkc > ul",
    "row_selector": ".scroll_main1 .zfxxgk_zdgkc > ul > li",
    "name_selector": ".scroll_main1 .zfxxgk_zdgkc > ul > li > a[title]",
    "duty_selector": "",
    "detail_link_selector": ".scroll_main1 .zfxxgk_zdgkc > ul > li > a[href][title]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "medium",
    "risk": "列表仅提供现任领导姓名，详情页仅含人口学简历且没有可回指的现职字段；姓名保留，依据说明按规则留空。",
}


def normalize_name(text: str) -> str:
    """去除姓名中的排版空格。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(text or "")).strip()


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导简介目录顺序提取明确姓名和真实详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for link in soup.select(
        ".scroll_main1 .zfxxgk_zdgkc > ul > li > a[href][title]"
    ):
        name = normalize_name(str(link.get("title") or link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": urljoin(base_url, str(link.get("href") or "")),
                "evidence": "",
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
