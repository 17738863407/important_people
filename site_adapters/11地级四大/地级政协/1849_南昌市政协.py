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
    "rule_id": "1849",
    "page_type": "人物文本列表页",
    "structure_group": "正文逐段姓名职务",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "NanchangCppccLeaderParagraphParser_v2",
    "leader_region_selector": ".content > p",
    "risk_flag": "二字姓名内部含排版空格，须按职务前缀边界拆分每段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一正文排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_name(value: str) -> str:
    """姓名字段仅去除排版空白。"""
    return "".join(_clean_text(value).split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """逐段按页面职务起始词边界拆分姓名和原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    pattern = re.compile(
        r"^\s*(?P<name>[\u4e00-\u9fff](?:[\s\xa0]*[\u4e00-\u9fff]){1,3})"
        r"[\s\xa0]+(?P<duty>(?:市政协|市委|省政府).+?)\s*$"
    )
    records: list[dict] = []
    seen: set[str] = set()
    for paragraph in soup.select(rule["leader_region_selector"]):
        raw_text = paragraph.get_text(" ", strip=True)
        match = pattern.fullmatch(raw_text)
        if match is None:
            continue
        name = _clean_name(match.group("name"))
        evidence = _clean_text(match.group("duty"))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": rule["parser"],
                "selector_summary": ".content直接p段落；按市政协/市委/省政府职务前缀拆分",
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
