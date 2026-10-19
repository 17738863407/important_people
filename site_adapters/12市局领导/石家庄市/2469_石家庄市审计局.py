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
    "rule_id": "2469", "page_type": "人物列表完整页", "structure_group": "sjz_audit_colon_title_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_audit_colon_title_v2",
    "leader_region_selector": "#conN内含多个冒号人物标题的直接子div容器",
    "name_selector": "标题div冒号前", "duty_selector": "标题div冒号后完整原文",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "每个标题后的主持或分管职责可跨多个div续行；页面另含非领导数据iframe",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅合并网页排版空白，不改变原始职务语义。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """仅解析姓名冒号职务标题div，排除数量不固定的后续职责div。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#conN")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")

    title_pattern = re.compile(r"^(?P<name>[\u3400-\u9fff·](?:\s*[\u3400-\u9fff·]){1,9})[：:](?P<duty>.+)$")
    candidates = []
    for container in regions[0].find_all("div", recursive=False):
        children = container.find_all("div", recursive=False)
        titles = [child for child in children if title_pattern.fullmatch(clean_text(child.get_text(" ", strip=True))) is not None]
        if len(titles) >= 2:
            candidates.append((children, titles))
    if len(candidates) != 1:
        raise RuntimeError(f"人物内容容器数量异常：{len(candidates)}")

    _, title_children = candidates[0]
    records: list[object] = []
    seen_names: set[str] = set()
    for title_node in title_children:
        title = clean_text(title_node.get_text(" ", strip=True))
        match = title_pattern.fullmatch(title)
        if match is None:
            raise RuntimeError(f"人物标题结构异常：{title}")
        name = re.sub(r"\s+", "", match.group("name"))
        evidence = clean_text(match.group("duty"))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or name in seen_names:
            raise RuntimeError(f"人物姓名、职务异常或姓名重复：{name}")
        if title_node.select_one("a[href]") is not None:
            raise RuntimeError(f"人物标题出现未审计链接：{name}")

        seen_names.add(name)
        records.append(PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"],
        ))
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
