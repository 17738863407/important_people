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
    "rule_id": "1747",
    "domain": "mzj.beijing.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "beijing_civil_affairs_cards_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_beijing_civil_affairs_cards_detail_v1",
    "risk_flag": "列表职务被拆成多个span且可能跨词边界，须按列表顺序从独立详情页姓名后的首个文本段读取完整职务",
    "confidence": "high",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩网页文本中的换行、全角空格和连续空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(value: str) -> str:
    """删除姓名中的排版空白。"""
    return re.sub(r"\s+", "", clean_text(value))


def extract_detail_duty(html: str, expected_name: str) -> str:
    """在详情正文中定位姓名段，并读取其后的首个非空职务段。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one("#zoom")
    if scope is None:
        return ""
    paragraphs = scope.select("p")
    for index, paragraph in enumerate(paragraphs):
        if clean_name(paragraph.get_text(" ", strip=True)) != expected_name:
            continue
        for duty_node in paragraphs[index + 1 :]:
            duty = clean_text(duty_node.get_text(" ", strip=True))
            if duty:
                return duty
        break
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按列表卡片原始顺序逐页取得可验证的完整职务。"""
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(".bjmz_member li"):
        link = item.select_one("a.bjmz_name[href]")
        name_node = item.select_one("span")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node is not None else "")
        if link is None or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, clean_text(str(link.get("href") or "")))
        try:
            response = session.get(detail_url, timeout=20)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            duty = extract_detail_duty(response.text, name)
        except requests.RequestException:
            continue
        if not duty:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".bjmz_member列表顺序及详情页#zoom姓名后首个职务段",
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
