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
    """跟随网页声明的当前领导页，再解析左侧职务与姓名分组。"""
    import requests
    from bs4 import BeautifulSoup

    source = final_url or str(page_rule.get("url", ""))
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select_one(".sl_xx"):
        match = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)", html)
        if not match:
            return []
        target = urljoin(source, match.group(1))
        session = requests.Session()
        session.trust_env = False
        response = session.get(target, timeout=35, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")
        source = response.url
    rows: list[dict[str, str]] = []
    for group in soup.select(".sl_xx .leader_list"):
        duty_node = group.select_one(".leader-position")
        duty = re.sub(r"[\s　\u2003:：]+", "", clean_text(duty_node.get_text(" ", strip=True) if duty_node else ""))
        for anchor in group.select(".leader-name a[href]"):
            name = clean_text(anchor.get_text(" ", strip=True)).replace(" ", "")
            if duty and re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                rows.append({"name": name, "duty": "", "evidence": duty,
                             "detail_url": urljoin(source, str(anchor.get("href") or "")),
                             "confidence": "high", "parser": "page_inline_lishui_government_menu_v1"})
    return rows


PAGE_RULE = {
    "rule_id": "3857", "page_type": "脚本跳转后的领导详情侧栏", "load_mode": "静态HTML含脚本跳转",
    "fetch_mode": "raw_http", "_fetch_mode_override": True, "extract_mode": "grouped_list",
    "parser": "page_inline_lishui_government_menu_v1", "leader_region_selector": ".sl_xx",
    "name_selector": ".leader-name a", "duty_selector": ".leader-position",
    "detail_link_selector": ".leader-name a[href]", "locator_strategy": "custom_parse_page",
    "risk_flag": "入口跳转至当前市长页侧栏", "confidence": "high",
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
