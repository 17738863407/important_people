from __future__ import annotations

import sys
import re
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4569",
    "page_type": "检察院领导简介段落",
    "structure_group": "tianjin_procuratorate_summary_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "summary_paragraphs",
    "parser": "page_tianjin_procuratorate_summary_paragraphs_v1",
    "leader_region_selector": "#fontzoom",
    "name_selector": "#fontzoom p首个冒号前",
    "duty_selector": "#fontzoom p首句冒号后",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "每人段落首句为姓名与职务摘要、后续为简历重复信息；仅取首句，并保留全部委员职务。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按正文中每个人物段落首句的“姓名：职务”结构提取。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one("#fontzoom")
    if region is None:
        raise RuntimeError("未找到院级领导正文 #fontzoom")
    rows: list[dict[str, str]] = []
    for paragraph in region.select("p"):
        text = re.sub(r"[\s\u00a0\u3000]+", "", paragraph.get_text(" ", strip=True))
        summary = re.split(r"[。.]", text, maxsplit=1)[0]
        match = re.match(r"^([\u3400-\u9fff·]{2,10})[：:](.+)$", summary)
        if match is None:
            continue
        name, evidence = match.group(1), match.group(2)
        parts = [part for part in re.split(r"[，,、；;]", evidence) if part]
        evidence = "、".join(parts)
        if not evidence:
            continue
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": "#fontzoom人物p按首句姓名冒号职务解析；简历重复段不参与，委员职务保留"})
    if not rows:
        raise RuntimeError("院级领导正文未提取到目标领导")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")


if __name__ == "__main__":
    main()
