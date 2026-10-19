from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse


PAGE_RULE = {
    "rule_id": "2529",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "ul.ldjs",
    "row_selector": "ul.ldjs > li",
    "name_selector": ".ldjs_r > p > span首行冒号后姓名",
    "duty_selector": ".ldjs_r > p > span首行冒号前原文",
    "detail_link_selector": ".ldjs_r a[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "职务与姓名位于同一span并以冒号分隔；必须逐li解析并使用规则主表注入机构核验归属。",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白，不改变字段语义。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def parse_page(html: str, final_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导列表DOM顺序动态拆分职务、姓名并取得同行详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    organization = clean_text(rule.get("organization", ""))
    if not organization:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in soup.select("ul.ldjs > li"):
        field_node = item.select_one(".ldjs_r > p > span")
        field_text = clean_text(field_node.get_text(" ", strip=True) if field_node is not None else "")
        match = re.fullmatch(r"(?P<duty>[^：:]{2,120})[：:](?P<name>[\u3400-\u9fff·]{2,8})", field_text)
        if match is None:
            continue
        duty = clean_text(match.group("duty"))
        name = match.group("name")
        if organization not in duty or name in seen_names:
            continue

        detail_node = item.select_one(".ldjs_r a[href]")
        detail_url = urljoin(final_url, clean_text(detail_node.get("href") if detail_node else ""))
        parsed_detail = urlparse(detail_url)
        if parsed_detail.scheme not in {"http", "https"} or detail_url.rstrip("/") == final_url.rstrip("/"):
            detail_url = ""

        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "henan_data_bureau_ldjs_rows_v1",
                "selector_summary": "scope=ul.ldjs>li；field=.ldjs_r>p>span首行；detail=.ldjs_r a[href]",
            }
        )
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
