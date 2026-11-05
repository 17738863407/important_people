from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4327",
    "page_type": "leader_page",
    "load_mode": "http",
    "parser": "custom",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "raw_http",
    "leader_region_selector": ".ldzc-list dl.leader-item",
    "risk": "只读取领导卡片h4姓名与领导职务强字段；工作分工不作职务，排除隐藏节点和页脚。",
    "confidence": "high",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    if not html:
        result = fetch_html_with_strategy(str(page_rule["url"]), "raw_http")
        html, final_url = result.html, result.final_url
    if "知道创宇云防御" in html or "客户端特征" in html:
        raise RuntimeError("在线入口页被知道创宇WAF拦截，未返回领导信息页面")
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for card in soup.select(str(page_rule["leader_region_selector"])):
        if any(node.has_attr("hidden") or node.get("aria-hidden") == "true" or re.search(r"display\s*:\s*none", str(node.get("style", "")), re.I) for node in [card, *card.parents] if getattr(node, "attrs", None) is not None):
            continue
        link = card.select_one("dt h4 a[href]")
        duty = ""
        for field in card.select("dd .infos"):
            label = field.select_one("label")
            value = field.select_one(".text")
            if label and value and label.get_text(strip=True).rstrip("：:") == "领导职务":
                duty = " ".join(value.get_text(" ", strip=True).split())
        name = re.sub(r"\s+", "", link.get_text() if link else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            raise RuntimeError("当前领导卡片缺少可靠姓名或领导职务字段")
        detail = urljoin(final_url, link["href"])
        if urlsplit(detail).netloc != urlsplit(final_url).netloc or not re.search(r"/\d{6}/[^/]+\.shtml$", urlsplit(detail).path):
            detail = ""
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail})
    if not rows:
        raise RuntimeError("当前页面未返回可见领导卡片")
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
