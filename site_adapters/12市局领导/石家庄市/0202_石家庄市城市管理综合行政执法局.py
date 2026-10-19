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
    "rule_id": "0202", "page_type": "人物列表完整页", "structure_group": "sjz_city_management_direct_paragraphs_v3",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_city_management_direct_paragraphs_v3",
    "leader_region_selector": "div#conN", "name_selector": "直接子p内首个职务片段之前的font文本",
    "duty_selector": "直接子p内首个职务片段起的原文", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "职责、分管和联系行不得误识别为人物职务",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文直接子段落顺序解析由多个font节点组成的姓名和原始职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("div#conN")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")
    records: list[object] = []
    seen_names: set[str] = set()
    duty_boundary = re.compile(r"党组|局长|调研员|纪检监察组组长")
    for node in regions[0].find_all("p", recursive=False):
        fragments = [clean_text(font.get_text("", strip=True)) for font in node.select("font")]
        fragments = [fragment for fragment in fragments if fragment]
        duty_index = next(
            (index for index, fragment in enumerate(fragments) if duty_boundary.search(fragment)),
            None,
        )
        if duty_index is None or duty_index == 0:
            continue
        name = clean_text("".join(fragments[:duty_index])).replace(" ", "")
        evidence = clean_text("".join(fragments[duty_index:]))
        if re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name) is None:
            continue
        if evidence.startswith(("负责", "分管", "联系", "主持")):
            continue
        if not evidence or name in seen_names:
            raise RuntimeError(f"人物职务为空或姓名重复：{name}")
        if node.select_one("a[href]") is not None:
            raise RuntimeError(f"人物标题行出现未审计链接：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("领导正文没有有效人物标题行")
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
