from __future__ import annotations

import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    text = " ".join(str(value or "").replace("\u3000", " ").split())
    return re.sub(r"([，、；：])\s+", r"\1", text)


def fetch_profile(item: tuple[str, str]) -> dict[str, str] | None:
    """读取详情简介块中的当前任职句。"""
    import requests
    from bs4 import BeautifulSoup

    name, url = item
    session = requests.Session()
    session.trust_env = False
    response = session.get(url, timeout=35, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "html.parser")
    content = soup.select_one("#UCAP-CONTENT")
    text = clean_text(content.get_text(" ", strip=True) if content else "")
    match = re.search(r"现任([^。]+)", text)
    duty = clean_text(match.group(1)) if match else ""
    if not duty:
        return None
    return {"name": name, "duty": "", "evidence": duty, "detail_url": response.url,
            "confidence": "high", "parser": "page_inline_linfen_government_details_v1"}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口列表DOM顺序并发读取每个人物详情，映射后恢复顺序。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    source = final_url or str(page_rule.get("url", ""))
    items = []
    for anchor in soup.select(".conWrap .con ul li.title a[href]"):
        name = clean_text(anchor.get_text(" ", strip=True)).replace(" ", "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            items.append((name, urljoin(source, str(anchor.get("href") or ""))))
    with ThreadPoolExecutor(max_workers=5) as pool:
        rows = list(pool.map(fetch_profile, items))
    return [row for row in rows if row]


PAGE_RULE = {
    "rule_id": "3854", "page_type": "目录转领导详情页", "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http", "_fetch_mode_override": True, "extract_mode": "list_to_detail",
    "parser": "page_inline_linfen_government_details_v1", "leader_region_selector": ".conWrap .con",
    "name_selector": "li.title a", "duty_selector": "#UCAP-CONTENT", "detail_link_selector": "li.title a[href]",
    "locator_strategy": "custom_parse_page", "risk_flag": "入口列表仅有姓名，需并发读取详情现任句",
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
