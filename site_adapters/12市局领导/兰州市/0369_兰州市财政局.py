from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0369",
    "page_type": "人物表格页",
    "structure_group": "lanzhou_finance_dash_title_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "collector": "raw_http",
    "parser": "page_lanzhou_finance_dash_title_table_v1",
    "leader_region_selector": "table.winstyle1578",
    "name_selector": "a.c1578标题横线后姓名",
    "duty_selector": "a.c1578标题横线前原始职务",
    "detail_link_selector": "a.c1578[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_list_links",
        "detail_link_selector": "table.winstyle1578 a.c1578[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "generic_captcha_token_in_valid_source_triggers_online_false_positive",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "table.winstyle1578",
            "row_selector": "tr",
            "leader_link_selector": "a.c1578[href]",
        },
        "api": {
            "enabled": False,
            "reason": "当前原始HTTP响应已直接包含完整领导表格；raw_http保留权威HTML并避免通用异常词误判",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def parse_title(title: str) -> tuple[str, str]:
    """按页面连续横线分隔符拆分原始职务和姓名。"""
    parts = re.split(r"(?:-{3,}|—{3,}|－{3,})", normalize_space(title), maxsplit=1)
    if len(parts) != 2:
        return "", ""
    duty = normalize_space(parts[0]).strip("，、；;")
    name = re.sub(r"\s+", "", normalize_space(parts[1]))
    if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
        return "", ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """仅在领导表格边界内按行提取标题两侧字段和人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.winstyle1578")
    if table is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in table.select("tr a.c1578[href]"):
        title = normalize_space(link.get_text(" ", strip=True))
        name, duty = parse_title(title)
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, str(link.get("href", "")).strip()),
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "table.winstyle1578逐行；a.c1578标题连续横线前后分别为原始职务和姓名；href为动态人物栏目页",
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
