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
    "rule_id": "2928",
    "page_type": "多人物详情合并页",
    "structure_group": "wulumuqi_science_nested_name_duty_pairs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "wulumuqi_science_nested_name_duty_pairs_v2",
    "leader_region_selector": "#NewsContent .gjnr",
    "name_selector": "聚合外层段内非空叶段姓名",
    "duty_selector": "姓名后相邻非空叶段的现任职务字段",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文存在聚合全文段及大量空白、图片段，需按非空叶段姓名与现任职务成对解析",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并正文叶段的排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按聚合外层段内非空叶段顺序解析姓名与现任职务对。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#NewsContent .gjnr")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文区域数量异常：{len(regions)}")
    wrappers = [
        node
        for node in regions[0].find_all("p", recursive=False)
        if node.find("p", recursive=False) is not None and "现任职务：" in node.get_text(" ", strip=True)
    ]
    if len(wrappers) != 1:
        raise RuntimeError(f"人物聚合外层段数量异常：{len(wrappers)}")
    leaf_texts = [
        clean_text(node.get_text(" ", strip=True))
        for node in wrappers[0].find_all("p")
        if node.find("p") is None and clean_text(node.get_text(" ", strip=True))
    ]
    if len(leaf_texts) % 2 != 0:
        raise RuntimeError(f"姓名与职务非空叶段数量不是偶数：{len(leaf_texts)}")

    records: list[object] = []
    seen_names: set[str] = set()
    for index in range(0, len(leaf_texts), 2):
        name = re.sub(r"\s+", "", leaf_texts[index])
        evidence = leaf_texts[index + 1]
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            raise RuntimeError(f"人物姓名叶段结构异常：{name}")
        if not evidence.startswith("现任职务：") or not evidence.removeprefix("现任职务：").strip():
            raise RuntimeError(f"人物职务叶段结构异常：{name}={evidence}")
        if name in seen_names:
            raise RuntimeError(f"人物姓名重复：{name}")
        duty = re.sub(r"[（(]挂职[）)]", "", evidence.removeprefix("现任职务：").strip()).strip("，、； ")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导正文没有可验证姓名与职务对")
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
