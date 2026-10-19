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
    "rule_id": "3045",
    "page_type": "多人物详情合并页",
    "structure_group": "xm_petition_inline_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_petition_inline_profiles_v2",
    "leader_region_selector": ".gl_div .TRS_Editor",
    "name_selector": ".gl_div .TRS_Editor p",
    "duty_selector": ".gl_div .TRS_Editor p内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "简介与分工交替排列，须仅在当前人物简介段提取完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文段落顺序提取人物姓名及对应的完整现任句。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("领导正文缺少 .gl_div .TRS_Editor")
    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in region.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        profile = re.match(r"^([\u3400-\u9fff·]{2,10})[，,].*?(现任[^。]*。)", text)
        if profile is None:
            continue
        name = profile.group(1)
        evidence = clean_text(profile.group(2))
        duty = evidence.removeprefix("现任").rstrip("。").strip()
        if name in seen_names:
            raise RuntimeError(f"领导简介姓名重复：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导正文中未提取到含完整现任句的人物简介")
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
