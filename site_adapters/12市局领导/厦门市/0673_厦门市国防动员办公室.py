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
    "rule_id": "0673",
    "page_type": "多人物详情合并页",
    "structure_group": "xm_gdb_inline_profile_blocks_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_gdb_inline_profile_blocks_v2",
    "leader_region_selector": "div.bd > div.szf_rr",
    "name_selector": "div.szf_con",
    "duty_selector": "div.szf_con",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "工作分工区段以现任句开头并续接分管内容；姓名取个人简历区段，只保留完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物块顺序从简历区提取姓名、从工作区提取完整现任句。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[object] = []
    seen: set[str] = set()
    for block in soup.select(page_rule["leader_region_selector"]):
        sections = [clean_text(node.get_text(" ", strip=True)) for node in block.select("div.szf_con")]
        biography = next((text for text in sections if text.startswith("个人简历")), "")
        work = next((text for text in sections if text.startswith("工作分工")), "")
        name_match = re.match(r"个人简历\s*(?P<name>[\u3400-\u9fff·]{2,10})(?:\s|[，,])", biography)
        evidence_match = re.search(r"现任[^。]*。", work)
        if name_match is None or evidence_match is None:
            raise RuntimeError("人物块缺少可核对的姓名或完整现任句")
        name = name_match.group("name")
        if name in seen:
            raise RuntimeError(f"人物姓名重复：{name}")
        evidence = re.sub(r"^现任\s*", "", evidence_match.group(0)).removesuffix("。")
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
