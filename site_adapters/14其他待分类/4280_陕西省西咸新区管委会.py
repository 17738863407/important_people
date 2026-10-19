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
    "rule_id": "4280", "page_type": "领导侧栏详情列表", "structure_group": "西咸新区领导之窗侧栏人物详情", "load_mode": "静态HTML直出", "extract_mode": "list_detail", "parser": "page_inline_xixian_leaders_v1", "leader_region_selector": ".m-lst-nav .w-nav", "name_selector": ".m-lst-nav .w-nav a[href]", "duty_selector": "详情页 .leader-ab 的职务字段", "detail_link_selector": ".m-lst-nav .w-nav a[href]", "detail_strategy": {"required": True, "mode": "list_link"}, "risk_flag": "入口只显示当前一名领导，全部现任人员须依左侧人物导航逐条读取详情，不能采入领导活动。", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """依人物导航顺序读取每页强结构姓名和职务字段。"""
    from bs4 import BeautifulSoup
    import requests
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session(); session.trust_env = False; session.headers["User-Agent"] = "Mozilla/5.0"
    rows: list[dict[str, str]] = []
    base_url = final_url or str(page_rule["url"])
    for link in soup.select(".m-lst-nav .w-nav a[href]"):
        detail_url = urljoin(base_url, link["href"])
        try:
            response = session.get(detail_url, timeout=20); response.raise_for_status()
        except requests.RequestException:
            continue
        response.encoding = response.apparent_encoding or "utf-8"
        detail = BeautifulSoup(response.text, "html.parser")
        box = detail.select_one(".leader-ab")
        if not box:
            continue
        name_node = box.select_one(".name")
        labels = box.select(".tnm")
        if not name_node:
            continue
        duty_node = next((label.find_next_sibling(class_="txt") for label in labels if label.get_text(strip=True) == "职务："), None)
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = re.sub(r"\s+", "", duty_node.get_text(" ", strip=True)) if duty_node else ""
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) and duty:
            verified_detail_url = "" if detail_url.rstrip("/") == base_url.rstrip("/") else detail_url
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": verified_detail_url, "parser": page_rule["parser"], "selector_summary": "领导侧栏链接 + 详情职务字段"})
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
