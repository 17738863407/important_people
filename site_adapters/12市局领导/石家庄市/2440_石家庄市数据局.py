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
    "rule_id": "2440", "page_type": "人物列表完整页", "structure_group": "sjz_data_strong_title_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_data_strong_title_v2",
    "leader_region_selector": "#conN内含多个strong人物标题的最深直接子容器",
    "name_selector": "标题div唯一strong文本的首个排版空白前",
    "duty_selector": "标题div唯一strong文本的首个排版空白后", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面另含非领导数据iframe；人物标题、职责说明和空行交替出现",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅合并网页排版空白，不改变原始职务语义。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析人物标题strong，忽略其后的主持、分管、协助职责和空行。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#conN")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")

    candidates = []
    for container in regions[0].find_all("div"):
        children = container.find_all("div", recursive=False)
        title_children = [child for child in children if child.find("strong") is not None]
        if len(title_children) >= 2:
            candidates.append((children, title_children))
    if len(candidates) != 1:
        raise RuntimeError(f"人物内容容器数量异常：{len(candidates)}")

    direct_children, title_children = candidates[0]
    records: list[object] = []
    seen_names: set[str] = set()
    title_pattern = re.compile(r"^(?P<name>[\u3400-\u9fff·]{2,10})\s+(?P<duty>.+)$")
    for line in direct_children:
        strong_nodes = line.find_all("strong")
        if not strong_nodes:
            continue
        if len(strong_nodes) != 1:
            raise RuntimeError(f"人物标题行strong数量异常：{len(strong_nodes)}")
        title = clean_text(strong_nodes[0].get_text(" ", strip=True))
        match = title_pattern.fullmatch(title)
        if match is None:
            raise RuntimeError(f"人物标题无法按排版空白拆分：{title}")
        name = match.group("name")
        evidence = clean_text(match.group("duty"))
        if not evidence or name in seen_names:
            raise RuntimeError(f"人物职务为空或姓名重复：{name}")
        if line.select_one("a[href]") is not None:
            raise RuntimeError(f"人物标题行出现未审计链接：{name}")

        seen_names.add(name)
        records.append(PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"],
        ))

    if len(records) != len(title_children):
        raise RuntimeError(f"人物输出数量与标题行数量不一致：{len(records)} != {len(title_children)}")
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
