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
    "rule_id": "1767",
    "page_type": "人物表格页",
    "structure_group": "taiyuan_civil_affairs_leader_table_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_civil_affairs_leader_table_v2",
    "leader_region_selector": "#zoom table",
    "name_selector": "人物行第一单元格",
    "duty_selector": "人物行第三单元格主持、负责或协助之前的完整职务",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "第三单元格混合职务和长篇工作分工，须在主持、负责或协助起点前截断",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并表格单元格排版空白并清理标点两侧空格。"""
    text = re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"\s*([、，；：])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按表格行顺序提取姓名及工作说明前的完整原始职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    tables = soup.select("#zoom table")
    if len(tables) != 1:
        raise RuntimeError(f"领导表格数量异常：{len(tables)}")

    records: list[object] = []
    seen_names: set[str] = set()
    for row in tables[0].select("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) != 3:
            continue
        name = re.sub(r"\s+", "", clean_text(cells[0].get_text(" ", strip=True)))
        introduction = clean_text(cells[2].get_text(" ", strip=True))
        work_match = re.search(r"(?<![\u3400-\u9fff])(主持|负责|协助)", introduction)
        evidence = introduction[: work_match.start()].rstrip("，。； ") if work_match else ""
        if name == "成员":
            continue
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or name in seen_names:
            raise RuntimeError(f"人物姓名、职务异常或姓名重复：{name}")
        if row.select_one("a[href]") is not None:
            raise RuntimeError(f"人物表格行出现未审计链接：{name}")
        seen_names.add(name)
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
    if not records:
        raise RuntimeError("领导表格没有可验证人物行")
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
