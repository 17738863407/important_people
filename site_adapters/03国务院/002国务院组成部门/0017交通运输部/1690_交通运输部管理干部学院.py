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
    "rule_id": "1690",
    "page_type": "人物表格页",
    "structure_group": "院校领导图文表格",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MotmtiLeaderTableParser_v2",
    "leader_region_selector": ".content.newsList table",
    "name_selector": "td:nth-of-type(2) p:first-of-type",
    "duty_selector": "td:nth-of-type(2) p:first-of-type",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名与职务位于同一首段，必须按段尾姓名边界拆分；职责与分管段落不得作为职务依据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按院校领导表格DOM顺序拆分首段中的原始职务与段尾姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for table in soup.select(".content.newsList table"):
        heading = table.select_one("td:nth-of-type(2) p:first-of-type")
        heading_text = _clean_text(heading.get_text(" ", strip=True)) if heading else ""
        matched = re.fullmatch(
            r"(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff](?:\s*[\u4e00-\u9fff]){1,3})",
            heading_text,
        )
        if not matched:
            continue
        name = re.sub(r"\s+", "", matched.group("name"))
        evidence = _clean_text(matched.group("duty"))
        evidence = re.sub(r"\s*、\s*", "、", evidence).strip(" ，,")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".content.newsList table；第二列首段；段尾姓名边界；排除后续职责与分管段落",
            }
        )
    if not records:
        raise RuntimeError("院校领导图文表格未解析到人物记录")
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
