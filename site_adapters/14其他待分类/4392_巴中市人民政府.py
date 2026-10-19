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
    "rule_id": "4392",
    "page_type": "dynamic_label_detail",
    "load_mode": "http",
    "fetch_mode": "raw_http",
    "parser": "custom",
    "risk": "入口页通过首位领导脚本和公开标签接口加载市政府领导，职务需由各人物详情页动态取得。",
    "confidence": "high",
}


def _request_text(url: str, params: dict[str, str] | None = None) -> str:
    """使用不继承失效本机代理的会话读取公开页面。"""
    import requests

    session = requests.Session()
    session.trust_env = False
    response = session.get(
        url,
        params=params,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=25,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def _detail_row(detail_url: str) -> dict[str, str] | None:
    """从人物详情页的明确姓名和职务字段生成一条记录。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(_request_text(detail_url), "html.parser")
    name_node = soup.select_one("#myLeadName, .ld_name")
    duty_node = soup.select_one(".ld_position")
    name = name_node.get_text(" ", strip=True) if name_node else ""
    duty_parts = list(duty_node.stripped_strings) if duty_node else []
    duty = "；".join(part for part in duty_parts if part)
    if not name or not duty:
        return None
    return {"name": name, "duty": duty, "detail_url": detail_url}


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按官网市政府领导区顺序读取首位脚本、标签列表及人物详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one('[aria-label="市政府领导"]')
    if region is None:
        return []

    detail_urls: list[str] = []
    lead_script = region.select_one('script[src*="/ljgl/ldzc/sz/"]')
    if lead_script and lead_script.get("src"):
        script_text = _request_text(urljoin(final_url, lead_script["src"]))
        href_match = re.search(r'href="([^"]+)"', script_text)
        if href_match:
            detail_urls.append(urljoin(final_url, href_match.group(1)))

    holder = region.select_one('.j-label-list[data-setting*="leaderWins"]')
    if holder is None:
        return []
    setting = holder.get("data-setting", "")
    type_match = re.search(r"typeId\s*:\s*'([^']+)'", setting)
    remove_match = re.search(r"removeIds\s*:\s*'([^']+)'", setting)
    file_match = re.search(r"file\s*:\s*'([^']+)'", setting)
    if not type_match or not remove_match or not file_match:
        return []
    fragment = _request_text(
        urljoin(final_url, "/site/label/8888"),
        {
            "labelName": "leaderWins",
            "length": "50",
            "dataType": "HTML",
            "isAllSite": "false",
            "typeId": type_match.group(1),
            "removeIds": remove_match.group(1),
            "file": file_match.group(1),
        },
    )
    fragment_soup = BeautifulSoup(fragment, "html.parser")
    for link in fragment_soup.select("a[href]"):
        detail_url = urljoin(final_url, link["href"])
        if detail_url not in detail_urls:
            detail_urls.append(detail_url)

    rows: list[dict[str, str]] = []
    for detail_url in detail_urls:
        row = _detail_row(detail_url)
        if row is not None:
            rows.append(row)
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
