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
    "rule_id": "2744", "page_type": "人物列表完整页", "structure_group": "sjz_stats_named_fields_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_stats_named_fields_v2",
    "leader_region_selector": "#conN .tj_njldnr", "name_selector": ".tj_njldnr1",
    "duty_selector": ".tj_njldnr2", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"}, "risk_flag": "",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅合并网页排版空白，不改变原始职务语义。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按统计局人物项中的明确姓名与职务字段解析。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#conN")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")
    leader_box = regions[0].select_one(":scope > .tj_njld")
    if leader_box is None:
        raise RuntimeError("领导正文没有人物项")

    records: list[object] = []
    seen_names: set[str] = set()
    pending_name_node = None
    for item in leader_box.find_all(recursive=False):
        classes = item.get("class", [])
        if "tj_njldnr1" in classes:
            if pending_name_node is not None:
                raise RuntimeError("连续出现未配对的姓名字段")
            pending_name_node = item
            continue
        if "tj_njldnr" not in classes:
            continue

        name_nodes = item.select(".tj_njldnr1")
        duty_nodes = item.select(".tj_njldnr2")
        if len(duty_nodes) != 1 or (len(name_nodes) != 1 and pending_name_node is None):
            raise RuntimeError(f"人物项姓名或职务字段数量异常：{len(name_nodes)} {len(duty_nodes)}")
        if len(name_nodes) == 1 and pending_name_node is not None:
            raise RuntimeError("独立姓名字段与人物项姓名字段发生冲突")
        name_node = name_nodes[0] if name_nodes else pending_name_node
        pending_name_node = None
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True)))
        evidence = clean_text(duty_nodes[0].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or name in seen_names:
            raise RuntimeError(f"人物姓名、职务异常或姓名重复：{name}")
        if item.select_one("a[href]") is not None:
            raise RuntimeError(f"人物项出现未审计链接：{name}")

        seen_names.add(name)
        records.append(PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"],
        ))
    if pending_name_node is not None:
        raise RuntimeError("领导正文末尾存在未配对的姓名字段")
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
