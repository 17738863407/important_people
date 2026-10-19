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
    "rule_id": "2182",
    "page_type": "多人物详情合并页",
    "structure_group": "nanchang_defense_current_profile_text_blocks_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "custom_parse_page",
    "parser": "nanchang_defense_current_profile_paragraphs_v1",
    "leader_region_selector": "div.cont",
    "name_selector": "正文中含现任句的原子文本节点",
    "duty_selector": "正文中含现任句的原子文本节点",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "黄文金、万明简介是div直接文本而非p；须读取原子文本块并避免父容器重复全文",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """仅合并网页排版空白。"""
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def _extract_current_duty(text: str) -> str:
    """在当前简介段内截断职责起始短语，并删除固定“现任”标签。"""
    match = re.search(r"现任[^。]*", text)
    if not match:
        return ""
    current_text = match.group(0)
    duty = re.split(
        r"(?=[，；](?:主要负责|负责|分管|协助|联系))",
        current_text,
        maxsplit=1,
    )[0]
    return re.sub(r"^现任\s*", "", duty).strip("，； ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文段落顺序提取姓名及完整“现任……”原文句。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    regions = soup.select(page_rule["leader_region_selector"])
    if len(regions) != 1:
        raise RuntimeError(f"领导正文区域命中数量异常：{len(regions)}")

    organization = str(page_rule["organization"])
    records: list[object] = []
    seen_names: set[str] = set()
    for text_node in regions[0].find_all(string=True):
        text = _clean_text(str(text_node))
        name_match = re.match(r"([\u3400-\u9fff·]{2,10})，", text)
        evidence = _extract_current_duty(text)
        if not name_match or not evidence:
            continue
        name = name_match.group(1)
        if organization not in evidence:
            continue
        if name in seen_names:
            raise RuntimeError(f"领导姓名重复：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=organization,
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
        raise RuntimeError("领导正文中未找到可回指的现任职务句")
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
