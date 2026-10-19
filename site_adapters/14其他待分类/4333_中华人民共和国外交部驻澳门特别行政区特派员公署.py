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
    "rule_id": "4333",
    "page_type": "特派员简历列表页",
    "structure_group": "ocmfa_mo_commissioner_bio_list_v1",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_ocmfa_mo_commissioner_v1",
    "leader_region_selector": ".news-item li a[href]",
    "detail_strategy": {"required": True, "mode": "list_link"},
    "risk_flag": "仅抽取特派员简历栏目中的当前列表项，不扫描公署新闻。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "explicit_css_plus_regex",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """从简历栏目列表项动态提取现任特派员及其独立简历页。"""
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.select(".news-item li a[href]"):
        text = " ".join(node.get_text(" ", strip=True).split())
        matched = re.match(r"^([\u3400-\u9fff·]{2,8})(特派员)简历", text)
        if matched:
            return [{
                "name": matched.group(1),
                "duty": matched.group(2),
                "detail_url": urljoin(final_url, node.get("href", "")),
            }]
    raise RuntimeError("未在特派员简历栏目定位到‘姓名+特派员简历’列表项")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
