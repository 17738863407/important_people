from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1486",
    "page_type": "人物表格页",
    "structure_group": "表格人物块加粗姓名职务",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "online",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".article-content table",
    "name_selector": "strong",
    "duty_selector": "strong",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导分工",
        "end_anchor": "公开方式",
        "include_selectors": [".article-content table"],
        "exclude_selectors": ["img", "script", "style"],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "加粗标签存在嵌套和空节点，需按完整姓名职务文本去重",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    """压缩网页排版空白并清理首尾标点。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip(" ：:，,。.")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物块顺序解析加粗节点中的姓名和原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".article-content")
    if content is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for strong in content.select("table strong"):
        value = clean_text(strong.get_text(" ", strip=True))
        match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,4})\s+(?P<duty>.+)$", value)
        if match is None:
            continue
        name = match.group("name").replace(" ", "")
        duty = clean_text(match.group("duty"))
        if (
            not re.search(r"书记|局长|副局长|调研员", duty)
            or name in seen
        ):
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": ".article-content table人物块内完整strong姓名职务文本",
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
