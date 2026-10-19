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
    "rule_id": "0693",
    "page_type": "人物列表完整页",
    "structure_group": "gdjdj_team_intro_prefix_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".team",
    "name_selector": ".team li .name a[href]",
    "duty_selector": ".team li .content p",
    "detail_link_selector": ".team li .name a[href]",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "online误跟随正文location代码；使用原始HTTP响应，职务仅取同卡片姓名前文本",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _compact(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物卡片顺序解析姓名以及简介首句中姓名之前的职务。"""
    from bs4 import BeautifulSoup

    del page_rule
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(".team li"):
        name_node = item.select_one(".name a[href]")
        name = _compact(name_node.get_text(" ", strip=True) if name_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or name in seen:
            continue
        paragraph = next(
            (node for node in item.select(".content p") if _compact(node.get_text(" ", strip=True))),
            None,
        )
        intro = _compact(paragraph.get_text(" ", strip=True) if paragraph else "")
        first_clause = re.split(r"[，,]", intro, maxsplit=1)[0]
        if not first_clause.endswith(name):
            continue
        duty = first_clause[: -len(name)].strip("，,。；;：:")
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": first_clause,
                "detail_url": urljoin(final_url, name_node.get("href", "")),
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
