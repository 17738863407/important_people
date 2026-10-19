from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


PAGE_RULE: dict[str, Any] = {
    "rule_id": "1508",
    "page_type": "职务分组名单页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "#zoom",
    "parser_id": "custom_mct_current_leaders_between_headings_v1",
    "structure_group": "正文标题边界_职务冒号姓名",
    "confidence": "high",
    "risk_notes": "仅解析现任领导与联系方式标题之间的段落；排除单位简介、职责、联系方式及页脚二维码iframe。",
}


def _clean(value: str) -> str:
    normalized = value.replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"[\s\u200b-\u200d\u2060\ufeff]+", " ", normalized).strip()


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, Any],
) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    scopes = soup.select(page_rule["leader_region_selector"])
    if len(scopes) != 1:
        raise RuntimeError(f"正文容器数量异常：{len(scopes)}")

    in_leader_section = False
    found_end = False
    rows: list[dict[str, str]] = []
    for paragraph in scopes[0].select("p"):
        text = _clean(paragraph.get_text(" ", strip=True))
        compact = re.sub(r"\s+", "", text)
        if compact == "现任领导":
            in_leader_section = True
            continue
        if in_leader_section and compact == "联系方式":
            found_end = True
            break
        if not in_leader_section:
            continue
        match = re.fullmatch(
            r"(?P<duty>[^：:]+)[：:](?P<name>[\u3400-\u9fff·]{2,6})",
            compact,
        )
        if match is None:
            raise RuntimeError(f"现任领导区存在无法解析的段落：{text}")
        rows.append(
            {
                "name": match.group("name"),
                "duty": match.group("duty"),
                "detail_url": "",
            }
        )

    if not in_leader_section or not found_end:
        raise RuntimeError("未找到完整的现任领导正文边界")
    if not rows:
        raise RuntimeError("现任领导区未解析到人物")
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
