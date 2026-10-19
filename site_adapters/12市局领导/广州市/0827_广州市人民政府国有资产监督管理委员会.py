from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0827",
    "page_type": "人物表格页",
    "structure_group": "正文编号机构职务姓名连续文本",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "online",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".article-content p",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".article-content"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "机构、职务与姓名连续排列，需按编号及职务末尾边界拆分",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_compact_text(value: str) -> str:
    """移除网页排版空白，保留原有标点。"""
    return re.sub(r"[\s\u3000\xa0]+", "", str(value or ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析编号段落中的“机构名+职务+姓名”连续文本。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = "广州市人民政府国有资产监督管理委员会"
    paragraph_pattern = re.compile(
        rf"^\d+[.．]{re.escape(organization)}(?P<clause>[^，。]+)"
    )
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for paragraph in soup.select(".article-content p"):
        text = clean_compact_text(paragraph.get_text(" ", strip=True))
        match = paragraph_pattern.match(text)
        if match is None:
            continue
        clause = match.group("clause")
        name_length = 2 if len(clause) >= 3 and clause[-3] in "任长员记部委" else 3
        name = clause[-name_length:]
        duty = clause[:-name_length].strip("，,。；;：:")
        if (
            not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name)
            or not duty
            or name in seen
        ):
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": f"{organization}{duty}",
                "detail_url": "",
                "selector_summary": ".article-content编号段落内机构名后职务姓名连续文本",
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
