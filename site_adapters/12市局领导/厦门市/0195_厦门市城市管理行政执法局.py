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
    "rule_id": "0195",
    "page_type": "多人物详情合并页",
    "structure_group": "xm_cg_inline_profile_paragraph_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_cg_inline_profile_paragraph_v2",
    "leader_region_selector": "div.article_content",
    "name_selector": "p b",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物段落同时包含简历和分工；只在含姓名粗体节点的当前段落提取完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def clean_name(value: str) -> str:
    """清除姓名节点中的排版空白。"""
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文段落顺序提取粗体姓名及同段完整现任句。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(page_rule["leader_region_selector"])
    if content is None:
        return []
    records: list[object] = []
    seen: set[str] = set()
    for paragraph in content.select("p"):
        name_node = paragraph.find("b")
        if name_node is None:
            continue
        name = clean_name(name_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
            continue
        paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
        evidence_match = re.search(r"现任[^。]*。", paragraph_text)
        if evidence_match is None:
            raise RuntimeError(f"人物段落缺少完整现任句：{name}")
        evidence = re.sub(r"^现任\s*", "", evidence_match.group(0)).removesuffix("。").strip()
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
