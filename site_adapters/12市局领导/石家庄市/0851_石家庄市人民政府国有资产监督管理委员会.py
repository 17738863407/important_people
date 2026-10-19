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
    "rule_id": "0851", "page_type": "多人物详情合并页", "structure_group": "sjz_sasac_current_sentence_blocks_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_sasac_current_sentence_blocks_v2",
    "leader_region_selector": "#conN > div", "name_selector": "人物块首句逗号前",
    "duty_selector": "当前人物块完整现任句", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "后续负责和分管内容不得混入现任职务依据",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物块顺序提取块内姓名与完整“现任……”原句。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#conN")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")
    records: list[object] = []
    seen_names: set[str] = set()
    for node in regions[0].find_all("div", recursive=False):
        text = clean_text(node.get_text(" ", strip=True))
        if not text:
            continue
        name_match = re.match(r"(?P<name>[\u3400-\u9fff·]{2,10})[，,]", text)
        evidence_match = re.search(r"现任([^。]*)。", text)
        if name_match is None or evidence_match is None:
            raise RuntimeError(f"人物块缺少姓名或完整现任句：{text}")
        name = name_match.group("name")
        evidence = clean_text(evidence_match.group(1))
        if name in seen_names:
            raise RuntimeError(f"人物姓名重复：{name}")
        if node.select_one("a[href]") is not None:
            raise RuntimeError(f"人物块出现未审计链接：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("领导正文没有有效人物块")
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
