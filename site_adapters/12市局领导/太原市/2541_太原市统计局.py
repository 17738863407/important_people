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
    "rule_id": "2541",
    "page_type": "多人物详情合并页",
    "structure_group": "taiyuan_stats_profile_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_stats_profile_paragraphs_v2",
    "leader_region_selector": "#zoom",
    "name_selector": "每个人物简介段开头逗号前姓名",
    "duty_selector": "同一简介段内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同页合并多人物简历及职责；现任句必须在当前人物段内定位，不能扫描全文串人",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并简介段中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def clean_current_evidence(value: str) -> str:
    """仅删除已定位现职句句首的“现任”固定标签。"""
    return re.sub(r"^现任(?:职务)?\s*[：:]?\s*", "", value, count=1)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """逐人物简介段提取段首姓名和同段完整“现任……”句。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#zoom")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")
    name_pattern = re.compile(r"^(?P<name>[\u3400-\u9fff·]{2,10})[，,]")
    evidence_pattern = re.compile(r"现任[^。]*。")

    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in regions[0].select(":scope > p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        name_match = name_pattern.match(text)
        evidence_match = evidence_pattern.search(text)
        if name_match is None or evidence_match is None:
            raise RuntimeError(f"人物简介缺少段首姓名或同段现任句：{text}")
        name = name_match.group("name")
        evidence = clean_current_evidence(evidence_match.group(0))
        if name in seen_names:
            raise RuntimeError(f"人物姓名重复：{name}")
        if paragraph.select_one("a[href]") is not None:
            raise RuntimeError(f"人物简介段出现未审计链接：{name}")
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
        raise RuntimeError("领导正文没有可验证人物简介段")
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
