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
    "rule_id": "2510",
    "page_type": "多人物详情合并页",
    "structure_group": "xm_agriculture_inline_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_agriculture_inline_profiles_v2",
    "leader_region_selector": "div.contain",
    "name_selector": "含现任句的p开头姓名",
    "duty_selector": "同一p中的完整现任句",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "简介后连续分工内容较长；依据只取当前人物段落内完整现任句，不截断、不纳入分工",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文人物简介段落顺序提取姓名和完整现任句。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到农业农村局领导信息正文")
    records: list[object] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"(?P<name>[\u3400-\u9fff·]{2,10})\s*[，,]", text)
        evidence_match = re.search(r"现任[^。]*。", text)
        if name_match is None or evidence_match is None:
            continue
        name = name_match.group("name")
        if name in seen:
            raise RuntimeError(f"人物姓名重复：{name}")
        evidence = evidence_match.group(0).removeprefix("现任").removesuffix("。").rstrip()
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
