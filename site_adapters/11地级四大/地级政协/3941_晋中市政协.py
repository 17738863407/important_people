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
    "rule_id": "3941",
    "domain": "zx.sxjz.gov.cn",
    "page_type": "人物卡片列表",
    "structure_group": "jinzhong_cppcc_leader_list_2026",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_jinzhong_cppcc_leader_list_v1",
    "leader_region_selector": "ul.leaderList",
    "name_selector": "h3.title > a[href]",
    "duty_selector": "h3.title > span.job",
    "detail_link_selector": "h3.title > a[href]",
    "content_scope": {"include_selectors": ["ul.leaderList"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "卡片另含职责说明，职务必须限定为h3.title中的job字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "ul.leaderList",
            "item_selector": ":scope > li",
            "name_selector": "h3.title > a[href]",
            "duty_selector": "h3.title > span.job",
            "detail_link_selector": "h3.title > a[href]",
        },
        "api": {"enabled": False, "reason": "静态HTML卡片已含可回指姓名、完整职务和详情链接"},
    },
}


def normalize_text(value: str) -> str:
    """清理标题字段中的排版空白和末尾展示标点。"""
    return re.sub(r"[\s\u00a0\u200b\u3000]+", "", value or "").strip("：:。；; ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导卡片顺序提取标题区姓名、职务和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("ul.leaderList")
    if region is None:
        from crawler_core.fetcher import fetch_html_with_strategy

        raw_result = fetch_html_with_strategy(str(page_rule["url"]), strategy="raw_http")
        soup = BeautifulSoup(raw_result.html, "html.parser")
        final_url = raw_result.final_url
        region = soup.select_one("ul.leaderList")
    if region is None:
        raise RuntimeError("原始HTTP响应仍未找到政协领导列表 ul.leaderList")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in region.find_all("li", recursive=False):
        link = item.select_one("h3.title > a[href]")
        duty_node = item.select_one("h3.title > span.job")
        name = normalize_text(link.get_text(" ", strip=True) if link else "")
        duty = normalize_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url or str(page_rule.get("url", "")), str(link.get("href", ""))),
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "必要时复取原始HTTP响应；ul.leaderList>li；h3.title内job职务和姓名链接",
            }
        )
    if not rows:
        raise RuntimeError("政协领导列表未解析出有效姓名和职务")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
