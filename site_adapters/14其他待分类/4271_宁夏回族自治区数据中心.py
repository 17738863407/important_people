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
    "rule_id": "4271",
    "page_type": "领导之窗详情列表",
    "structure_group": "宁夏数据中心领导之窗详情页",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_detail",
    "parser": "page_inline_ningxia_data_center_leaders_v1",
    "leader_region_selector": ".pageList.newsList",
    "name_selector": "详情正文首段姓名",
    "duty_selector": ".view.TRS_UEDITOR p 中的现任句",
    "detail_link_selector": ".pageList.newsList a[href]",
    "detail_strategy": {"required": True, "mode": "list_link"},
    "risk_flag": "列表标题只有职务，须逐条读取当前详情正文；同职务条目应保留页面顺序。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从领导详情页正文首段提取姓名和现任职务。"""
    from bs4 import BeautifulSoup
    import requests

    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.trust_env = False
    session.headers["User-Agent"] = "Mozilla/5.0"
    rows: list[dict[str, str]] = []
    base_url = final_url or str(page_rule["url"])
    for link in soup.select(".pageList.newsList a[href]"):
        detail_url = urljoin(base_url, link["href"])
        try:
            response = session.get(detail_url, timeout=20)
            response.raise_for_status()
        except requests.RequestException:
            continue
        response.encoding = response.apparent_encoding or "utf-8"
        detail_soup = BeautifulSoup(response.text, "html.parser")
        body = detail_soup.select_one(".view.TRS_UEDITOR")
        if not body:
            continue
        text = re.sub(r"\s+", "", body.get_text(" ", strip=True))
        match = re.search(r"^([\u4e00-\u9fff]{2,4})[，,].*?现任(.+?)。", text)
        if not match:
            continue
        name, duty = match.groups()
        if not duty:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url, "parser": page_rule["parser"], "selector_summary": "领导目录链接 + 详情正文现任句"})
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
