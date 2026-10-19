from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2751",
    "page_type": "人物表格页",
    "structure_group": "xm_statistics_leader_tables_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "parser": "xm_statistics_leader_tables_v2",
    "leader_region_selector": "table.lead_table",
    "name_selector": "第二行第一格末个p",
    "duty_selector": "首行第二格中的完整现任句",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面模板含系统维护字样导致online误判；raw_http原始响应已核实包含完整权威表格，依据只取简介中的完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物表格顺序提取姓名和完整现任句。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.select(page_rule["leader_region_selector"])
    if not tables:
        raise RuntimeError("未找到统计局领导人物表格")
    records: list[object] = []
    seen: set[str] = set()
    for table in tables:
        rows = table.select("tr")
        if len(rows) < 2:
            raise RuntimeError("人物表格缺少简介行或角色行")
        intro_cells = rows[0].select("td")
        role_cells = rows[1].select("td")
        role_parts = role_cells[0].select("p") if role_cells else []
        if len(intro_cells) < 2 or len(role_parts) < 2:
            raise RuntimeError("人物表格缺少简介、短职务或姓名字段")
        intro = clean_text(intro_cells[1].get_text(" ", strip=True))
        name = re.sub(r"\s+", "", clean_text(role_parts[-1].get_text(" ", strip=True)))
        evidence_match = re.search(r"现任厦门市统计局[^。]*。", intro)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or evidence_match is None:
            raise RuntimeError("人物表格缺少有效姓名或完整现任句")
        if name in seen:
            raise RuntimeError(f"人物姓名重复：{name}")
        evidence = re.sub(
            r"^现任(?:职务)?[：:]?",
            "",
            evidence_match.group(0),
            count=1,
        )
        seen.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url="",
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
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
