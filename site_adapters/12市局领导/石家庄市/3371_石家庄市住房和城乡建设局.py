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
    "rule_id": "3371", "page_type": "人物列表完整页", "structure_group": "sjz_housing_comma_lines_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_housing_comma_lines_v2",
    "leader_region_selector": "#conN内含多个姓名逗号职务行的最深直接子div容器",
    "name_selector": "人物div首个逗号前", "duty_selector": "人物div首个逗号后",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物div之间存在空排版div",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def compact_text(value: str) -> str:
    """移除人物行中的排版空白，不改变汉字和标点。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析非空的姓名逗号职务人物div，并排除间隔空行。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#conN")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")
    pattern = re.compile(r"^(?P<name>[\u3400-\u9fff·]{2,10})[，,](?P<evidence>.+)$")
    candidates = []
    for container in regions[0].find_all("div"):
        children = container.find_all("div", recursive=False)
        person_nodes = [child for child in children if pattern.fullmatch(compact_text(child.get_text(" ", strip=True))) is not None]
        if len(person_nodes) >= 2:
            candidates.append((children, person_nodes))
    if len(candidates) != 1:
        raise RuntimeError(f"人物内容容器数量异常：{len(candidates)}")

    _, person_nodes = candidates[0]
    records: list[object] = []
    seen_names: set[str] = set()
    for node in person_nodes:
        text = compact_text(node.get_text(" ", strip=True))
        match = pattern.fullmatch(text)
        if match is None:
            raise RuntimeError(f"人物行结构异常：{text}")
        name = match.group("name")
        evidence = match.group("evidence")
        if not evidence or name in seen_names:
            raise RuntimeError(f"人物职务为空或姓名重复：{name}")
        if node.select_one("a[href]") is not None:
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
