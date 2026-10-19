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
    "rule_id": "1484", "page_type": "人物列表完整页", "structure_group": "sjz_forestry_alternating_sentences_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_forestry_alternating_sentences_v2",
    "leader_region_selector": "#conN > div", "name_selector": "每组人物行首个逗号前",
    "duty_selector": "每组人物行首个逗号后完整原文", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物行与工作分工行交替；原始职务已含机构名，不得删除",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按交替结构解析人物行并保留含机构名的完整原始职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#conN")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")
    lines = regions[0].find_all("div", recursive=False)
    if not lines or len(lines) % 2 != 0:
        raise RuntimeError(f"人物与工作分工行数量不是偶数：{len(lines)}")
    records: list[object] = []
    seen_names: set[str] = set()
    for index in range(0, len(lines), 2):
        title = clean_text(lines[index].get_text(" ", strip=True))
        work = clean_text(lines[index + 1].get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>[\u3400-\u9fff·\s]{2,15})[，,](?P<duty>.+。)", title)
        if match is None or not work:
            raise RuntimeError(f"人物行或工作分工行结构异常：{title}")
        name = re.sub(r"\s+", "", match.group("name"))
        evidence = clean_text(match.group("duty")).removesuffix("。").strip()
        if not evidence or name in seen_names:
            raise RuntimeError(f"人物职务为空或姓名重复：{name}")
        if lines[index].select_one("a[href]") is not None:
            raise RuntimeError(f"人物行出现未审计链接：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
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
