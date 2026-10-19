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
    "rule_id": "2883",
    "page_type": "人物文本列表页",
    "structure_group": "正文逐段姓名职务",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "WuhanCppccLeaderParagraphParser_v2",
    "leader_region_selector": ".list_ld__R .TRS_UEDITOR p",
    "risk_flag": "增强HTTP会脚本跳转至政协搜索页，二字姓名含排版空格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _compact_text(value: str) -> str:
    """仅移除姓名职务段落中的排版空白。"""
    return "".join(str(value or "").replace("\u3000", " ").replace("\u2002", " ").replace("\xa0", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """逐段按职务起始词边界拆分姓名及原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for paragraph in soup.select(rule["leader_region_selector"]):
        text = _compact_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff]{2,4})(?P<duty>(?:市政协|市委).+)", text)
        if match is None or match.group("name") in seen:
            continue
        name = match.group("name")
        evidence = match.group("duty")
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": rule["parser"],
                "selector_summary": ".list_ld__R .TRS_UEDITOR直接人物段落",
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
