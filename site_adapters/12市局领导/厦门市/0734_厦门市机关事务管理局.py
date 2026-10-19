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
    "rule_id": "0734",
    "page_type": "人物表格页",
    "structure_group": "xm_jgsw_inline_profile_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_jgsw_inline_profile_paragraphs_v2",
    "leader_region_selector": "#trsContent",
    "name_selector": "p",
    "duty_selector": "p",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文同时含简历和分工段落；只解析以姓名、性别开头且含完整现任句的简介段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文简介段落顺序提取姓名和完整现任句。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(page_rule["leader_region_selector"])
    if content is None:
        raise RuntimeError("未找到领导信息正文 #trsContent")

    records: list[object] = []
    seen: set[str] = set()
    for paragraph in content.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"(?P<name>[\u3400-\u9fff·]{2,10})\s*[，,]\s*[男女](?:\s|[，,])", text)
        evidence_match = re.search(r"现任[^。]*。", text)
        if name_match is None or evidence_match is None:
            continue
        name = name_match.group("name")
        if name in seen:
            raise RuntimeError(f"人物姓名重复：{name}")
        evidence = re.sub(r"^现任\s*", "", evidence_match.group(0)).rstrip("。")
        seen.add(name)
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
        raise RuntimeError("正文中未提取到含完整现任句的人物简介")
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
