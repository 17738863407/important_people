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
    "rule_id": "0527",
    "page_type": "多人物详情合并页",
    "structure_group": "xm_fao_four_paragraph_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_fao_four_paragraph_profiles_v2",
    "leader_region_selector": ".TRS_Editor",
    "name_selector": "p",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文按标题、简历、现任句、分工四段循环；用相邻同名简历校验人物边界，只取现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def clean_evidence(value: str) -> str:
    """删除现任标签和纯句末句号，并归一化中文标点旁排版空格。"""
    text = re.sub(r"^现任\s*", "", clean_text(value))
    text = re.sub(r"\s*([、，；：])\s*", r"\1", text)
    return text.rstrip("。 ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按相邻同名简历校验标题，并提取后续完整现任句。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(page_rule["leader_region_selector"])
    if content is None:
        return []
    paragraphs = [
        clean_text(node.get_text(" ", strip=True))
        for node in content.select("p")
        if clean_text(node.get_text(" ", strip=True))
    ]
    records: list[object] = []
    seen: set[str] = set()
    for index, heading in enumerate(paragraphs[:-2]):
        heading_match = re.fullmatch(r"(?P<name>[\u3400-\u9fff·]{2,10})\s+.+", heading)
        if heading_match is None:
            continue
        name = heading_match.group("name")
        biography = paragraphs[index + 1]
        if re.match(rf"{re.escape(name)}[，,]", biography) is None:
            continue
        evidence = next(
            (
                match.group(0)
                for text in paragraphs[index + 2 : index + 4]
                if (match := re.search(r"现任[^。]*。", text)) is not None
            ),
            "",
        )
        if not evidence:
            raise RuntimeError(f"人物简介后缺少完整现任句：{name}")
        evidence = clean_evidence(evidence)
        if name in seen:
            raise RuntimeError(f"人物姓名重复：{name}")
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
