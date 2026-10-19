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
    "rule_id": "4424",
    "page_type": "领导简介文章段落",
    "structure_group": "qinghai_court_comma_profile_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "custom_parse_page",
    "parser": "qinghai_court_comma_profile_paragraphs_v1",
    "leader_region_selector": ".detail > .text",
    "name_selector": ".detail > .text > p段首姓名、性别字段",
    "duty_selector": ".detail > .text > p内现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文含来源标记和空段；仅解析段首姓名、性别结构且同段存在现任句的人物段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理段落排版空白及中文标点两侧空格。"""
    cleaned = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"\s*([，。；、：])\s*", r"\1", cleaned)


def parse_person_paragraph(text: str) -> tuple[str, str] | None:
    """从单个人物简介段落中提取姓名与现任职务。"""
    value = clean_text(text)
    if "现任" not in value:
        return None
    name_match = re.match(r"^(?P<name>[\u3400-\u9fff·]{2,10})，[男女]，", value)
    if name_match is None:
        return None
    name = name_match.group("name")
    evidence = clean_text(value.split("现任", 1)[1]).rstrip("。；; ")
    if not evidence:
        raise RuntimeError(f"人物简介段落的现任职务字段为空：{name}")
    return name, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文段落顺序抽取人物姓名和段内现任职务证据。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    article = soup.select_one(".detail > .text")
    if article is None:
        raise RuntimeError("未定位到法院文章正文")

    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in article.select(":scope > p"):
        parsed = parse_person_paragraph(paragraph.get_text(" ", strip=True))
        if parsed is None:
            continue
        name, evidence = parsed
        if name in seen_names:
            raise RuntimeError(f"人物段落姓名重复：{name}")
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
        raise RuntimeError("当前文章未提取到含现任职务的人物段落")
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
