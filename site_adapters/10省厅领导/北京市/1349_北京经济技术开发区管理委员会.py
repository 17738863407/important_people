from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1349",
    "domain": "kfqgw.beijing.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "beijing_edz_management_committee_tab_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "browser_dom",
    "parser": "page_inline_beijing_edz_management_committee_tab_v1",
    "risk_flag": "同页分工委领导和管委会领导两组，必须只取明确标注的管委会领导标签组",
    "confidence": "high",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩网页文本中的换行、全角空格和连续空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(value: str) -> str:
    """删除姓名中的排版空白。"""
    return re.sub(r"\s+", "", clean_text(value))


def fetch_detail_html(session: requests.Session, url: str) -> str:
    """在线取得当前人物详情页HTML。"""
    response = session.get(url, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def extract_detail_fields(html: str) -> tuple[str, str]:
    """从详情页标题区读取强结构姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    detail = soup.select_one(".details_page.ld")
    if detail is None:
        return "", ""
    name_node = detail.select_one("h2 p.title")
    duty_node = name_node.find_next_sibling("p") if name_node is not None else None
    name = clean_name(name_node.get_text(" ", strip=True) if name_node is not None else "")
    duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node is not None else "")
    duty = re.sub(r"[（(]\s*挂职\s*[）)]", "", duty)
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按“管委会领导”标签组的原始顺序逐页取得姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    tab = soup.select_one('#ld_tab > li[data-type="1"]')
    if tab is None or clean_text(tab.get_text(" ", strip=True)) != "管委会领导":
        return []
    group = tab.find_next_sibling("div", attrs={"data-type": "1"})
    if group is None:
        return []

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    visited_urls: set[str] = set()

    for link in group.select('a[href*="/ldjs/gwhld/20"]'):
        list_name = clean_name(link.get("title") or link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, clean_text(str(link.get("href") or "")))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", list_name) or detail_url in visited_urls:
            continue
        visited_urls.add(detail_url)

        try:
            name, duty = extract_detail_fields(fetch_detail_html(session, detail_url))
        except requests.RequestException:
            continue
        name = name or list_name
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen_names:
            continue

        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "管委会领导data-type=1标签组链接及详情页h2标题区",
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
