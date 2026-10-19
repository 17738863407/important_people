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


def add_row(
    rows: list[dict[str, str]],
    name: str,
    duty: str,
    href: str,
    source: str,
) -> None:
    """加入一个已由强结构栏目定位的人物记录。"""
    normalized_name = clean_text(name).replace(" ", "")
    normalized_duty = clean_text(duty)
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", normalized_name) or not normalized_duty:
        return
    rows.append(
        {
            "name": normalized_name,
            "duty": "",
            "evidence": normalized_duty,
            "detail_url": urljoin(source, href),
            "confidence": "high",
            "parser": "page_inline_jining_government_leaders_v1",
        }
    )


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """解析政府公开首页中按市长、副市长、秘书长展示的领导区。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    source = final_url or str(page_rule.get("url", ""))
    if not soup.select_one(".main1-left"):
        leader_index = next(
            (
                anchor
                for anchor in soup.select("a[href]")
                if clean_text(anchor.get_text(" ", strip=True)) == "领导专页"
            ),
            None,
        )
        redirect_html = html
        redirect_source = source
        if leader_index:
            import requests

            index_url = urljoin(source, str(leader_index.get("href") or ""))
            session = requests.Session()
            session.trust_env = False
            index_response = session.get(
                index_url,
                timeout=35,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            index_response.raise_for_status()
            index_response.encoding = index_response.apparent_encoding
            redirect_html = index_response.text
            redirect_source = index_response.url
        redirect_match = re.search(
            r"window\.location\.href\s*=\s*[\"']([^\"']+)",
            redirect_html,
        )
        if redirect_match:
            import requests

            redirect_url = urljoin(redirect_source, redirect_match.group(1))
            session = requests.Session()
            session.trust_env = False
            response = session.get(
                redirect_url,
                timeout=35,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, "html.parser")
            source = response.url
    rows: list[dict[str, str]] = []

    mayor = soup.select_one(".main1-left1-con p")
    if mayor:
        duty_node = mayor.select_one("span")
        anchor = mayor.select_one("a[href]")
        if duty_node and anchor:
            add_row(rows, anchor.get_text(" ", strip=True), duty_node.get_text(" ", strip=True), str(anchor.get("href") or ""), source)

    for group in soup.select(".main1-left2 li"):
        duty_node = group.select_one("span")
        duty = duty_node.get_text(" ", strip=True) if duty_node else ""
        for anchor in group.select("a[href]"):
            add_row(rows, anchor.get_text(" ", strip=True), duty, str(anchor.get("href") or ""), source)
    return rows


PAGE_RULE = {
    "rule_id": "3844",
    "page_type": "脚本跳转后的政府领导分组",
    "load_mode": "静态HTML含脚本跳转",
    "extract_mode": "grouped_list",
    "parser": "page_inline_jining_government_leaders_v1",
    "leader_region_selector": ".main1-left",
    "name_selector": ".main1-left1-con p a, .main1-left2 li a",
    "duty_selector": ".main1-left1-con p span, .main1-left2 li span",
    "detail_link_selector": ".main1-left a[href]",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "入口页经站内脚本跳转至当前领导区",
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
