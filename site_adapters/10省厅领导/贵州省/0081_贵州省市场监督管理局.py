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
    "rule_id": "0081",
    "page_type": "人物列表完整页",
    "structure_group": "gz_amr_leader_list_fields_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".ldzc_left ul",
    "name_selector": ".ldzc_left li a[href] h3",
    "duty_selector": ".ldzc_left li a[href] p span",
    "detail_link_selector": ".ldzc_left li a[href]",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "右侧正文重复首位人物；只解析左侧完整领导目录的强字段节点",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按左侧完整领导目录顺序读取姓名、职务节点和详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    entry_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".ldzc_left li a[href]"):
        name_node = link.select_one("h3")
        duty_node = link.select_one("p span")
        name = _clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").rstrip("。").strip()
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(entry_url, str(link.get("href", ""))),
            }
        )

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
