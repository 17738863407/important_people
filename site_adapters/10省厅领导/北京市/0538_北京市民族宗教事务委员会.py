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
    "rule_id": "0538",
    "page_type": "人物列表完整页",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "parser": "beijing_ethnic_religious_leader_list_v3",
    "leader_region_selector": ".ldjs ul li",
    "name_selector": "li直属文本节点",
    "duty_selector": ".zhiwu",
    "detail_link_selector": "",
    "locator_strategy": "custom_parse_page",
    "filter_policy": "strong_no_wordlist",
    "confidence": "high",
    "risk_flag": "姓名含全角空格，读取li直属文本并去除排版空白",
}


def _clean_text(value: object) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按列表DOM顺序提取li直属姓名文本和明确.zhiwu字段。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[PersonRecord] = []
    seen_names: set[str] = set()
    for item in soup.select(page_rule["leader_region_selector"]):
        duty_node = item.select_one(page_rule["duty_selector"])
        direct_text = "".join(str(node) for node in item.find_all(string=True, recursive=False))
        name = re.sub(r"\s+", "", direct_text)
        duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence=page_rule["confidence"],
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
