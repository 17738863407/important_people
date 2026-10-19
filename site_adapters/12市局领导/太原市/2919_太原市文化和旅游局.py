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
    "rule_id": "2919",
    "page_type": "人物列表完整页",
    "structure_group": "taiyuan_culture_leader_list_items_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_culture_leader_list_items_v2",
    "leader_region_selector": "#Zoom ul.list-paddingleft-2",
    "name_selector": "人物列表项段首括号前姓名",
    "duty_selector": "人物列表项段首括号内完整职务",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物列表上方另有标题及聚合文本，列表项括号后为长篇工作分工",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并列表项排版空白并清理标点与括号两侧空格。"""
    text = re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"\s*([、，；：（）()])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按列表项DOM顺序解析段首姓名和括号内完整职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    lists = soup.select("#Zoom ul.list-paddingleft-2")
    if len(lists) != 1:
        raise RuntimeError(f"领导列表数量异常：{len(lists)}")
    pattern = re.compile(
        r"^(?P<name>[\u3400-\u9fff·](?:\s*[\u3400-\u9fff·]){1,9})[（(]"
        r"(?P<evidence>[^（）()]+)[）)][:：]"
    )

    records: list[object] = []
    seen_names: set[str] = set()
    for item in lists[0].select(":scope > li"):
        text = clean_text(item.get_text(" ", strip=True))
        match = pattern.match(text)
        if match is None:
            raise RuntimeError(f"人物列表项结构异常：{text}")
        name = re.sub(r"\s+", "", match.group("name"))
        evidence = clean_text(match.group("evidence"))
        if not evidence or name in seen_names:
            raise RuntimeError(f"人物职务异常或姓名重复：{name}")
        if item.select_one("a[href]") is not None:
            raise RuntimeError(f"人物列表项出现未审计链接：{name}")
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
        raise RuntimeError("领导列表没有可验证人物项")
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
