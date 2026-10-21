from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4285", "page_type": "市委领导导航详情页", "structure_group": "丽水市委领导左侧分类导航", "load_mode": "静态HTML直出", "extract_mode": "list_detail", "parser": "page_inline_lishui_party_leaders_v1", "leader_region_selector": ".sl_xx .sl_ul1", "name_selector": ".sl_xx .leader-name a[href]", "duty_selector": "详情页 .xx_job", "detail_link_selector": ".sl_xx .leader-name a[href]", "detail_strategy": {"required": True, "mode": "list_link"}, "risk_flag": "导航卡片只有书记、副书记、常委分类，必须从各自详情页的现职字段读取完整职务。", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按市委领导导航顺序动态读取详情页现职字段。"""
    from bs4 import BeautifulSoup
    import requests
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session(); session.trust_env = False; session.headers["User-Agent"] = "Mozilla/5.0"
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    source_url = (final_url or str(page_rule["url"])).rstrip("/")
    for link in soup.select(".sl_xx .leader-name a[href]"):
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        detail_url = urljoin(source_url + "/", link["href"])
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or name in seen:
            continue
        try:
            response = session.get(detail_url, timeout=20, verify=False); response.raise_for_status()
        except requests.RequestException:
            continue
        response.encoding = response.apparent_encoding or "utf-8"
        detail = BeautifulSoup(response.text, "html.parser")
        duty_node = detail.select_one(".xx_job")
        duty = re.sub(r"\s+", "", duty_node.get_text(" ", strip=True)) if duty_node else ""
        if duty:
            seen.add(name)
            is_entry_page = urlparse(detail_url).path.rstrip("/") == (urlparse(source_url).path.rstrip("/") + "/index.html")
            verified_detail_url = "" if is_entry_page else detail_url
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": verified_detail_url, "parser": page_rule["parser"], "selector_summary": "市委领导导航链接 + 详情现职字段"})
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
