from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def clean_text(value: str) -> str:
    """压缩详情页职务字段的排版空白。"""
    text = " ".join((value or "").replace("\u3000", " ").split())
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return re.sub(r"([，。；：、（）])\s+", r"\1", text)


def parse_detail(detail_html: str, expected_name: str) -> str:
    """校验详情页标题姓名并取得首个“职务”字段。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    root = soup.select_one(".leader-details")
    if root is None:
        return ""
    name_node = root.select_one("h2.leader-tit")
    detail_name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
    if detail_name != expected_name:
        return ""
    first_group = root.select_one(".wrap_right > dl")
    cells = first_group.select(":scope > dd") if first_group else []
    return clean_text(cells[1].get_text(" ", strip=True)) if len(cells) >= 2 else ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按目录顺序在线读取每个人物详情页的明确职务字段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select("a[href]"):
        name = clean_text(link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if (
            not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name)
            or not re.search(r"/ldjj/20\d{4}/t20\d{6}_\d+\.html$", detail_url)
            or name in seen
        ):
            continue
        seen.add(name)
        duty = ""
        try:
            detail_result = fetch_html_with_strategy(detail_url, "raw_http")
            duty = parse_detail(detail_result.html, name)
        except Exception:
            duty = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high" if duty else "medium",
                "parser": "page_inline_changsha_affairs_directory_detail_v1",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2595",
    "page_type": "人物目录详情页",
    "structure_group": "changsha_affairs_directory_detail",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_changsha_affairs_directory_detail_v1",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "职务只存在于独立详情页；目录姓名必须与详情页 h2.leader-tit 一致",
    "confidence": "high",
}


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
