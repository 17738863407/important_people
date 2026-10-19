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
    "rule_id": "1998",
    "page_type": "人物列表完整页",
    "structure_group": "nsbd_current_leader_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "parser": "nsbd_current_leader_paragraphs_v2",
    "leader_region_selector": ".TRS_Editor",
    "name_selector": ".TRS_Editor > p",
    "duty_selector": ".TRS_Editor > p",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "一、现任领导",
        "end_anchor": "二、内设机构",
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文下半部为内设机构；必须在两个标题之间按人物段落解析",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析现任领导标题至内设机构标题之间的姓名职务段落。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = next(
        (
            node
            for node in soup.select(page_rule["leader_region_selector"])
            if node.find("p", recursive=False) is not None
        ),
        None,
    )
    if region is None:
        return []

    scope = page_rule["content_scope"]
    in_leader_scope = False
    records: list[object] = []
    seen: set[str] = set()
    for paragraph in region.find_all("p", recursive=False):
        label = _clean_text(paragraph.get_text(" ", strip=True))
        if label == scope["start_anchor"]:
            in_leader_scope = True
            continue
        if label == scope["end_anchor"]:
            break
        if not in_leader_scope:
            continue
        match = re.fullmatch(
            r"(?P<name>[\u3400-\u9fff·\s]{2,20})[：:](?P<duty>.+)",
            label,
        )
        if match is None:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = _clean_text(match.group("duty"))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or not duty or name in seen:
            continue
        seen.add(name)
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
