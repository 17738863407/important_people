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
    "rule_id": "2893",
    "page_type": "人物表格页",
    "structure_group": "hefei_health_leader_assignment_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "browser_render_wait_ms": 8000,
    "fetch_mode": "playwright",
    "extract_mode": "custom_parse_page",
    "parser": "hefei_health_leader_assignment_paragraphs_v1",
    "leader_region_selector": "div.j-fontContent.newscontnet",
    "name_selector": "p.MsoNormal",
    "duty_selector": "p.MsoNormal",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "普通HTTP返回521；正文每段在姓名后混有分工和电话，须仅解析“职务+姓名+同志”前缀",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """仅合并网页排版空白和标点前空白。"""
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：、（）])", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文人物段顺序提取“职务+姓名+同志”前缀，排除后续职责。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    regions = soup.select(page_rule["leader_region_selector"])
    if len(regions) != 1:
        raise RuntimeError(f"领导正文区域命中数量异常：{len(regions)}")

    role_boundary = r"书记|主任|调研员|局长"
    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in regions[0].select(page_rule["name_selector"]):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        prefix = text.split("同志", 1)[0].replace(" ", "") if "同志" in text else ""
        match = re.fullmatch(
            rf"(?P<duty>.*?(?:{role_boundary}))(?P<name>[\u3400-\u9fff·]{{2,4}})",
            prefix,
        )
        if not match:
            continue
        name = match.group("name")
        evidence = match.group("duty")
        if name in seen_names:
            raise RuntimeError(f"领导姓名重复：{name}")
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
        raise RuntimeError("领导正文中未找到可核验的职务姓名前缀")
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
