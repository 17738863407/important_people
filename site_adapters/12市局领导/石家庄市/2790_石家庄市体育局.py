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
    "rule_id": "2790", "page_type": "人物列表完整页", "structure_group": "sjz_sports_numbered_lines_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_sports_numbered_lines_v2",
    "leader_region_selector": "#conN内含多个编号行的最深直接子div容器",
    "name_selector": "编号后至逗号", "duty_selector": "逗号后至冒号",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "冒号后为主持、分管、负责或协助职责；页面另含非领导数据iframe",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅合并网页排版空白，不改变原始职务语义。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """在编号人物行内按逗号和冒号边界提取姓名、职务并排除职责。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#conN")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")
    pattern = re.compile(
        r"^(?P<order>\d+)[.．、]\s*(?P<name>[\u3400-\u9fff·](?:\s*[\u3400-\u9fff·]){1,9})[，,]"
        r"(?P<duty>[^：:]+)[：:](?P<responsibility>.+)$"
    )
    candidates = []
    for container in regions[0].find_all("div"):
        children = container.find_all("div", recursive=False)
        lines = [child for child in children if pattern.fullmatch(clean_text(child.get_text(" ", strip=True))) is not None]
        if len(lines) >= 2:
            candidates.append(lines)
    if len(candidates) != 1:
        raise RuntimeError(f"编号人物内容容器数量异常：{len(candidates)}")

    records: list[object] = []
    seen_names: set[str] = set()
    for expected_order, line in enumerate(candidates[0], start=1):
        text = clean_text(line.get_text(" ", strip=True))
        match = pattern.fullmatch(text)
        if match is None or int(match.group("order")) != expected_order:
            raise RuntimeError(f"编号人物行结构或次序异常：{text}")
        name = re.sub(r"\s+", "", match.group("name"))
        evidence = clean_text(match.group("duty"))
        responsibility = clean_text(match.group("responsibility"))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or name in seen_names:
            raise RuntimeError(f"人物姓名、职务异常或姓名重复：{name}")
        if not responsibility.startswith(("主持", "分管", "负责", "协助")):
            raise RuntimeError(f"人物职责字段边界异常：{name} {responsibility}")
        if line.select_one("a[href]") is not None:
            raise RuntimeError(f"人物行出现未审计链接：{name}")

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
