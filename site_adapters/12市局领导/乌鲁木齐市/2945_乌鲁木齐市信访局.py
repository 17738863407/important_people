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
    "rule_id": "2945",
    "page_type": "人物列表完整页",
    "structure_group": "wulumuqi_petition_name_next_duty_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "wulumuqi_petition_name_next_duty_v2",
    "leader_region_selector": "#NewsContent .gjnr",
    "name_selector": "独立姓名段",
    "duty_selector": "姓名后的紧邻非空职务段",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "每组职务后紧随主持、分管和负责等职责段，职责不得并入主职务证据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性合并正文排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按非空段落顺序解析独立姓名及其紧邻原始职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#NewsContent .gjnr")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文区域数量异常：{len(regions)}")
    paragraphs = [
        (paragraph, clean_text(paragraph.get_text(" ", strip=True)))
        for paragraph in regions[0].select("p")
        if clean_text(paragraph.get_text(" ", strip=True))
    ]

    records: list[object] = []
    seen_names: set[str] = set()
    for index, (paragraph, text) in enumerate(paragraphs[:-1]):
        name = text.replace(" ", "")
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None:
            continue
        duty_paragraph, evidence = paragraphs[index + 1]
        if not evidence.startswith("市信访局"):
            raise RuntimeError(f"姓名后的紧邻段不是预期职务：{name}")
        if name in seen_names:
            raise RuntimeError(f"人物姓名重复：{name}")
        if paragraph.select_one("a[href]") is not None or duty_paragraph.select_one("a[href]") is not None:
            raise RuntimeError(f"人物或职务段出现未审计链接：{name}")
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
        raise RuntimeError("领导正文没有可验证的姓名与紧邻职务组")
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
