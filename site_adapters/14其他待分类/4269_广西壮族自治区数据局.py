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
    "rule_id": "4269",
    "page_type": "领导信息详情列表",
    "structure_group": "广西数据局领导信息公开详情列表",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_detail",
    "parser": "page_inline_guangxi_data_leaders_v1",
    "leader_region_selector": ".zfxxgk-more-list",
    "name_selector": ".zfxxgk-more-list a[href]",
    "duty_selector": "详情页当前任职句",
    "detail_link_selector": ".zfxxgk-more-list a[href]",
    "detail_strategy": {"required": True, "mode": "list_link"},
    "risk_flag": "领导目录仅展示姓名，现职须逐条从当前人物详情页的现任句取得。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录顺序抓取当前人物详情页中的现任职务句。"""
    from bs4 import BeautifulSoup
    import requests

    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.trust_env = False
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    base_url = final_url or str(page_rule["url"])
    for link in soup.select(".zfxxgk-more-list a[href]"):
        name = re.sub(r"[\s\u200b]+", "", link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(base_url, link["href"])
        try:
            response = session.get(detail_url, timeout=20)
            response.raise_for_status()
        except requests.RequestException:
            continue
        response.encoding = response.apparent_encoding or "utf-8"
        detail_soup = BeautifulSoup(response.text, "html.parser")
        sentence = next(
            (
                node.strip()
                for node in detail_soup.stripped_strings
                if "现任" in node and "。" in node
            ),
            "",
        )
        match = re.search(r"现任\s*(.+?)。", sentence)
        if not match:
            continue
        duty = re.sub(r"\s+", "", match.group(1)).strip()
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": page_rule["parser"],
                "selector_summary": "领导目录链接 + 详情页现任句",
            }
        )
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
