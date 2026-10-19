from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1815",
    "page_type": "人物表格页",
    "structure_group": "栏目元数据人物数组与详情双列表格",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "list_detail",
    "collector": "online",
    "parser": "builtin_parse_page",
    "leader_region_selector": "栏目元数据children数组",
    "name_selector": "children[].name",
    "duty_selector": "详情页表格左列姓名后职务段落",
    "detail_link_selector": "children[].pub_point",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "工作分工",
        "include_selectors": ["table tr:first-child td:first-child"],
        "exclude_selectors": ["img", "script", "style"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "api_children_detail",
        "meta_url": "http://mzzjj.gz.gov.cn/postmeta/s/13446.json",
    },
    "risk_flag": "规则入口跳转首位人物，须由栏目元数据动态发现全部详情页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    """压缩网页排版空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_detail(html: str, expected_name: str) -> tuple[str, str]:
    """从人物详情页双列表格左列提取姓名及完整原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    for table_row in soup.select("table tr"):
        cells = table_row.find_all(["th", "td"], recursive=False)
        if len(cells) < 2 or "工作分工" not in clean_text(cells[1].get_text(" ", strip=True)):
            continue
        left_cell = cells[0]
        strong = left_cell.select_one("strong")
        name = clean_text(strong.get_text(" ", strip=True)).replace(" ", "") if strong else ""
        if name != expected_name:
            continue
        duty_parts: list[str] = []
        passed_name = False
        for paragraph in left_cell.select("p"):
            paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
            if not paragraph_text:
                continue
            if not passed_name:
                if paragraph_text.replace(" ", "") == name:
                    passed_name = True
                continue
            duty_parts.append(paragraph_text)
        duty = clean_text(" ".join(duty_parts))
        return name, duty
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按栏目元数据数组顺序发现并解析当前全部人物详情页。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    detail_strategy = page_rule.get("detail_strategy", {})
    meta_url = str(detail_strategy.get("meta_url", ""))
    meta_result = fetch_html_with_strategy(meta_url, "raw_http")
    meta_data = json.loads(meta_result.html)
    children = meta_data.get("children", [])
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for child in children:
        name = clean_text(child.get("name", "")).replace(" ", "")
        pub_point = clean_text(child.get("pub_point", "")).strip("/")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or not pub_point or name in seen:
            continue
        detail_url = urljoin(str(page_rule.get("url", "")), f"/{pub_point}/")
        detail_result = fetch_html_with_strategy(detail_url, "online")
        parsed_name, duty = parse_detail(detail_result.html, name)
        if parsed_name != name or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_result.final_url,
                "selector_summary": "栏目元数据children顺序及详情页双列表格左列姓名后职务段落",
            }
        )
        seen.add(name)

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
