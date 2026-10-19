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
    "rule_id": "0714",
    "page_type": "人物列表完整页",
    "structure_group": "taiyuan_natural_resources_leader_title_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_natural_resources_leader_title_v2",
    "leader_region_selector": "div.box_list",
    "name_selector": "领导信息分组a[title]冒号前姓名",
    "duty_selector": "领导信息分组a[title]冒号后完整职务",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同页另有机构职能和内设机构同结构分组，必须限定领导信息分组",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并title属性中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """仅解析标题为“领导信息”的分组内姓名与职务title。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    groups = [
        box
        for box in soup.select("div.box_list")
        if clean_text((box.select_one(".title") or box).get_text(" ", strip=True)) == "领导信息"
    ]
    if len(groups) != 1:
        raise RuntimeError(f"领导信息分组数量异常：{len(groups)}")
    pattern = re.compile(r"^(?P<name>[\u3400-\u9fff·\s]{2,12})[:：](?P<evidence>.+)$")

    records: list[object] = []
    seen_names: set[str] = set()
    for node in groups[0].select("a[title]"):
        title = clean_text(str(node.get("title", "")))
        match = pattern.fullmatch(title)
        if match is None:
            raise RuntimeError(f"领导title结构异常：{title}")
        name = re.sub(r"\s+", "", match.group("name"))
        evidence = clean_text(match.group("evidence"))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or name in seen_names:
            raise RuntimeError(f"人物姓名、职务异常或姓名重复：{name}")
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
        raise RuntimeError("领导信息分组没有可验证人物title")
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
