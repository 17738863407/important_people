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


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """调用页面脚本公开声明的 leaderPositions HTML接口。"""
    import requests
    from bs4 import BeautifulSoup

    source = final_url or str(page_rule.get("url", ""))
    endpoint = urljoin(source, "/site/label/8888")
    session = requests.Session()
    session.trust_env = False
    response = session.get(endpoint, params={
        "labelName": "leaderPositions", "id": "4450232", "length": 20,
        "isDate": "true", "file": "/longnan/leaderInfo-ln-szfld-news",
    }, timeout=35, headers={"User-Agent": "Mozilla/5.0", "Referer": source})
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "html.parser")
    rows: list[dict[str, str]] = []
    for anchor in soup.select("li > a[href]"):
        name_node = anchor.select_one(".ld-name")
        duty_node = anchor.select_one(".ld-title")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) and duty:
            rows.append({"name": name, "duty": "", "evidence": duty,
                         "detail_url": urljoin(source, str(anchor.get("href") or "")),
                         "confidence": "high", "parser": "page_inline_longnan_leader_api_v1"})
    return rows


PAGE_RULE = {
    "rule_id": "3858", "page_type": "异步HTML接口领导卡片", "load_mode": "静态壳页加公开接口",
    "fetch_mode": "raw_http", "_fetch_mode_override": True, "extract_mode": "html_api",
    "parser": "page_inline_longnan_leader_api_v1", "leader_region_selector": ".ld-listBox[aria-label='市政府领导']",
    "name_selector": ".ld-name", "duty_selector": ".ld-title", "detail_link_selector": "li > a[href]",
    "locator_strategy": "custom_parse_page", "risk_flag": "页面通过leaderPositions接口异步加载",
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
