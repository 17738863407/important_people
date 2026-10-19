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
    "rule_id": "2078",
    "page_type": "人物表格页",
    "structure_group": "xm_port_leader_profile_tables_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_port_leader_profile_tables_v2",
    "leader_region_selector": ".TRS_Editor",
    "name_selector": "每个人物表格简介行开头姓名",
    "duty_selector": "同一表格首行姓名后的职务原文",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "历史版本硬编码人物结果；现按7个独立人物表格动态解析，并用简介姓名校验首行姓名",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理HTML排版空白，并合并中文字符间的版式空格。"""
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()
    previous = ""
    while previous != text:
        previous = text
        text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)
    return re.sub(r"\s+([，。；、])", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物表格顺序动态提取简介姓名与首行原始职务。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.select(f'{page_rule["leader_region_selector"]} table')
    if not tables:
        raise RuntimeError("未找到领导信息人物表格")
    records: list[object] = []
    seen: set[str] = set()
    for table in tables:
        table_text = clean_text(table.get_text(" ", strip=True))
        intro_match = re.search(r"简介[：:]\s*(?P<name>[\u3400-\u9fff·]{2,10})[，,]", table_text)
        first_row = table.select_one("tr")
        cells = first_row.select("td") if first_row is not None else []
        headline = clean_text(cells[-1].get_text(" ", strip=True)) if cells else ""
        if intro_match is None or not headline:
            raise RuntimeError("人物表格缺少简介姓名或首行职务")
        name = intro_match.group("name")
        if not headline.startswith(name):
            raise RuntimeError(f"人物首行与简介姓名不一致：{name}")
        evidence = headline[len(name) :].strip()
        if evidence.startswith("现任"):
            evidence = evidence[len("现任") :].strip()
        evidence = re.sub(r"。$", "", evidence).strip()
        if not evidence or name in seen:
            raise RuntimeError(f"人物职务缺失或姓名重复：{name}")
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
