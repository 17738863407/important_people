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
    "rule_id": "1405",
    "page_type": "职务分组名单页",
    "structure_group": "lanzhou_government_leader_groups",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "leader_region_selector": "div.ldjs_box",
    "name_selector": "div.shizhang a[href] p, div.fushizhang a[href] p",
    "duty_selector": "div.shizhang h4, div.fushizhang h4",
    "detail_link_selector": "div.shizhang a[href], div.fushizhang a[href]",
    "risk_flag": "同页还含市委书记、副书记和常委，必须排除非市政府分组",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(text: str) -> str:
    """清理页面用于姓名和职务排版的空白字符。"""
    return re.sub(r"\s+", "", text or "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """仅解析市长、副市长和市政府秘书长分组。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("div.ldjs_box")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for group in region.select("div.shizhang, div.fushizhang"):
        title = group.select_one("h4")
        duty = clean_text(title.get_text(" ", strip=True) if title else "")
        if not duty:
            continue
        for link in group.select("a[href]"):
            name_node = link.select_one("p")
            name = clean_text(name_node.get_text(" ", strip=True) if name_node else link.get_text(" ", strip=True))
            detail_url = urljoin(final_url, str(link.get("href") or "").strip())
            if not re.fullmatch(r"[一-鿿·]{2,4}", name) or not detail_url or detail_url in seen_urls:
                continue
            seen_urls.add(detail_url)
            rows.append(
                {
                    "order": str(len(rows) + 1),
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": detail_url,
                    "confidence": str(page_rule.get("confidence") or "high"),
                    "parser": "inline_lanzhou_government_leader_groups_v1",
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
