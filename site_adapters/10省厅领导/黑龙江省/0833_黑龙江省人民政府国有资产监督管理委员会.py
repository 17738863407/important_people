from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0833",
    "page_type": "人物表格页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "div.ld-list",
    "row_selector": "div.ld-list a[href*='/c104222/']",
    "name_selector": "div.ld-list a[href*='/c104222/'] > p",
    "duty_selector": "详情页#zoomcon中的职务字段",
    "detail_link_selector": "div.ld-list a[href*='/c104222/']",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "原始HTML中的领导容器隐藏且为空，必须浏览器渲染；列表仅含姓名和日期，职务须按列表顺序在线访问详情页并限定#zoomcon职务—分工边界。",
}


def normalize_text(text: str) -> str:
    """仅压缩网页字段中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def normalize_name(text: str) -> str:
    """去除姓名中的排版空格。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(text or "")).strip()


def extract_detail_duty(html: str, expected_name: str) -> tuple[str, str]:
    """核对详情标题姓名，并提取正文中职务与分工之间的明确字段。"""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one("h1.article_title")
    if normalize_name(title.get_text(" ", strip=True) if title is not None else "") != expected_name:
        return "", ""
    scope = soup.select_one("#zoomcon")
    text = normalize_text(scope.get_text(" ", strip=True) if scope is not None else "")
    match = re.search(r"职务\s*[：:]\s*(.+?)\s*分工\s*[：:]", text)
    if match is None:
        return "", ""
    duty = normalize_text(match.group(1))
    return duty, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按渲染后的领导列表顺序在线读取各详情页职务。"""
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    failed_details: list[str] = []

    for link in soup.select("div.ld-list a[href*='/c104222/']"):
        name_node = link.select_one(":scope > p")
        name = normalize_name(name_node.get_text(" ", strip=True) if name_node is not None else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        try:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
        except requests.RequestException as error:
            failed_details.append(f"{name}：{error}")
            continue
        duty, evidence = extract_detail_duty(response.text, name)
        if not duty or not evidence:
            failed_details.append(f"{name}：详情页缺少可验证的职务—分工字段")
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
            }
        )

    if failed_details:
        raise RuntimeError("领导详情解析失败：" + "；".join(failed_details))
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
