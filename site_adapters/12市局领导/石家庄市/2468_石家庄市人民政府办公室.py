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
    "rule_id": "2468", "page_type": "多人物详情合并页", "structure_group": "sjz_gov_profile_responsive_duplicate_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_gov_profile_responsive_duplicate_v2",
    "leader_region_selector": ".pcys #conN, .ipys #conN", "name_selector": "#conN直接子div第1项",
    "duty_selector": "#conN直接子div第2项中的完整现任原文", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同一人物内容在pcys与ipys响应式布局中重复直出，须按姓名与现任原文去重",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅合并网页排版空白，不改变原始现任证据。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析响应式重复布局中的姓名与完整现任原文，并稳定去重。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select(".pcys #conN, .ipys #conN")
    if not regions:
        raise RuntimeError("未找到领导简介响应式内容块")

    records: list[object] = []
    seen_rows: set[tuple[str, str]] = set()
    for region in regions:
        fields = region.find_all("div", recursive=False)
        if len(fields) != 2:
            raise RuntimeError(f"领导简介字段数量异常：{len(fields)}")
        name = re.sub(r"\s+", "", clean_text(fields[0].get_text(" ", strip=True)))
        evidence = clean_text(fields[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence.startswith("现任"):
            raise RuntimeError(f"领导简介姓名或现任原文异常：{name} {evidence}")
        if region.select_one("a[href]") is not None:
            raise RuntimeError(f"领导简介出现未审计链接：{name}")
        identity = (name, evidence)
        if identity in seen_rows:
            continue
        seen_rows.add(identity)
        evidence = re.sub(r"。$", "", re.sub(r"^现任\s*", "", evidence)).strip()
        records.append(PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"],
        ))
    if not records:
        raise RuntimeError("响应式内容块去重后没有人物")
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
