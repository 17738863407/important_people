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
    "rule_id": "0731",
    "page_type": "现任领导信息页",
    "structure_group": "姓名与机构职务连续段落",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MofTreasuryLeaderParagraphParser_v2",
    "leader_region_selector": ".TRS_Editor p",
    "risk_flag": "姓名内部含字距空白，页面无人物详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _compact_text(value: str) -> str:
    """仅清除段落中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", str(value or "")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按正文段落顺序，以页面机构职务前缀切分姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for paragraph in soup.select(rule["leader_region_selector"]):
        compact_text = _compact_text(paragraph.get_text("", strip=False))
        match = re.fullmatch(r"([\u4e00-\u9fff·]{2,8})((?:国库司|国库支付中心).+)", compact_text)
        if not match:
            continue
        name, duty = match.groups()
        duty = re.sub(r"[（(]\s*挂职\s*[）)]", "", duty).strip()
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
                "selector_summary": ".TRS_Editor人物段落；机构职务前缀切分姓名与职务",
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
