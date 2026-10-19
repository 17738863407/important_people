from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2236",
    "page_type": "人物目录详情页",
    "structure_group": "正文直接子块多空白分隔职务姓名",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MofSocialSecurityLeaderWhitespaceParser_v2",
    "leader_region_selector": ".conabout .TRS_Editor > div",
    "risk_flag": "职务和姓名内部含单字距空白，必须以连续多空白作为字段边界",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _compact_field(value: str) -> str:
    """移除字段内部用于字距排版的空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", str(value or "")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按正文直接子块顺序解析连续多空白分隔的职务与姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for block in soup.select(rule["leader_region_selector"]):
        text = block.get_text("", strip=False).strip()
        match = re.fullmatch(r"(.+?)[\s\u00a0\u3000]{2,}([\u4e00-\u9fff·\s\u00a0\u3000]{2,12})", text)
        if not match:
            continue
        duty = _compact_field(match.group(1))
        name = _compact_field(match.group(2))
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": rule["parser"],
                "selector_summary": ".conabout .TRS_Editor直接子块；连续多空白字段边界",
            }
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
