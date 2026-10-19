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
    "rule_id": "0110",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "parser": "beijing_subcenter_leader_paragraph_v3",
    "leader_region_selector": "div.cont_txt div.view",
    "name_selector": "p strong:first-of-type",
    "duty_selector": "p中姓名节点之后的原始文本",
    "detail_link_selector": "",
    "locator_strategy": "custom_parse_page",
    "filter_policy": "strong_no_wordlist",
    "confidence": "high",
    "risk_flag": "",
}


def _clean_text(value: object) -> str:
    """仅规范排版空白，不删除原文标点。"""
    text = str(value or "").replace("\u00a0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def _clean_evidence(value: object) -> str:
    """删除独立任职状态标记和纯句末句号，保留全部具体职务。"""
    cleaned = re.sub(
        r"(?:<|＜|\(|（)\s*(?:挂职|兼|主持日常工作)\s*(?:>|＞|\)|）)",
        "",
        _clean_text(value),
    )
    cleaned = re.sub(r"\s*([、，；])\s*", r"\1", cleaned)
    return cleaned.removesuffix("。").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文段落DOM顺序提取姓名和姓名后的完整原始职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    records: list[PersonRecord] = []
    seen_names: set[str] = set()
    for paragraph in region.select("p"):
        name_node = paragraph.select_one("strong:first-of-type")
        if name_node is None:
            continue
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True)))
        paragraph_text = _clean_text(paragraph.get_text(" ", strip=True))
        duty = _clean_evidence(paragraph_text[len(_clean_text(name_node.get_text(" ", strip=True))):])
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
