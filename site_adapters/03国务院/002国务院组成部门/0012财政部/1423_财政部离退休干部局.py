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
    "rule_id": "1423",
    "page_type": "多人物详情合并页",
    "structure_group": "正文段落职务姓名行",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MofRetiredCadresLeaderParagraphParser_v2",
    "leader_region_selector": ".conabout .TRS_Editor p",
    "risk_flag": "入口页正文直接列出人物但不提供独立详情链接，详情页必须留空",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _normalize_space(value: str) -> str:
    """将全角和不换行空格等排版字距归一为单个空格。"""
    return re.sub(r"[\s\u00a0\u3000\u2002-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按正文段落顺序解析每行末尾姓名及前置职务。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for paragraph in soup.select(rule["leader_region_selector"]):
        text = _normalize_space(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(.+)\s+([\u4e00-\u9fff·]{2,8})", text)
        if not match:
            continue
        duty, name = match.groups()
        if name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": rule["parser"],
                "selector_summary": ".conabout .TRS_Editor人物段落；末尾姓名词元",
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
