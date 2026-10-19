from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def to_http(url: str) -> str:
    """该站HTTPS存在异常椭圆曲线握手，读取同源HTTP页面。"""
    parts = urlsplit(url)
    return urlunsplit(("http", parts.netloc, parts.path, parts.query, parts.fragment))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """由当前详情页动态找到政府领导总览，再解析强结构卡片。"""
    import requests
    from bs4 import BeautifulSoup

    source = final_url or str(page_rule.get("url", ""))
    detail_soup = BeautifulSoup(html, "html.parser")
    index_anchor = next(
        (a for a in detail_soup.select("a[href]") if clean_text(a.get_text(" ", strip=True)) == "政府领导"),
        None,
    )
    if not index_anchor:
        return []
    index_url = to_http(urljoin(source, str(index_anchor.get("href") or "")))
    session = requests.Session()
    session.trust_env = False
    response = session.get(index_url, timeout=35, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "html.parser")
    rows: list[dict[str, str]] = []
    for anchor in soup.select(".xxgk-pageRight .leaderImg a.con[href]"):
        name_node = anchor.select_one(".name")
        duty_node = anchor.select_one(".duty")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
        rows.append({"name": name, "duty": "", "evidence": duty,
                     "detail_url": urljoin(response.url, str(anchor.get("href") or "")),
                     "confidence": "high", "parser": "page_inline_lincang_government_cards_v1"})
    return rows


PAGE_RULE = {
    "rule_id": "3853", "page_type": "详情页回溯领导总览", "load_mode": "浏览器读取HTTPS详情后同源HTTP总览",
    "fetch_mode": "playwright", "_fetch_mode_override": True, "extract_mode": "list",
    "parser": "page_inline_lincang_government_cards_v1", "leader_region_selector": ".xxgk-pageRight .leaderImg",
    "name_selector": "a.con .name", "duty_selector": "a.con .duty", "detail_link_selector": "a.con[href]",
    "locator_strategy": "custom_parse_page", "risk_flag": "HTTPS存在BAD_ECPOINT，站点同源HTTP可复现",
    "confidence": "high",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
