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
    "rule_id": "2316", "page_type": "人物列表完整页", "structure_group": "sjz_sfj_strong_title_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_sfj_strong_title_v2",
    "leader_region_selector": "#conN内含多个strong标题行的最深直接子容器",
    "name_selector": "人物标题div内唯一strong", "duty_selector": "同一标题div移除strong后的原文",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物标题后的职责div数量不固定；只解析含唯一strong的标题div",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅合并网页排版空白，不改变原始职务语义。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按标题div中的唯一strong提取姓名，并排除其后的职责说明div。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#conN")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")

    candidates = []
    for container in regions[0].find_all("div"):
        direct_children = container.find_all("div", recursive=False)
        title_children = [child for child in direct_children if child.find("strong") is not None]
        if len(title_children) >= 2:
            candidates.append((container, direct_children, title_children))
    if len(candidates) != 1:
        raise RuntimeError(f"人物内容容器数量异常：{len(candidates)}")

    _, direct_children, title_children = candidates[0]
    records: list[object] = []
    seen_names: set[str] = set()
    for line in direct_children:
        strong_nodes = line.find_all("strong")
        if not strong_nodes:
            continue
        if len(strong_nodes) != 1:
            raise RuntimeError(f"人物标题行strong数量异常：{len(strong_nodes)}")

        name = re.sub(r"\s+", "", clean_text(strong_nodes[0].get_text(" ", strip=True)))
        line_copy = BeautifulSoup(str(line), "html.parser")
        copied_strong = line_copy.find("strong")
        if copied_strong is None:
            raise RuntimeError("复制人物标题行后未找到strong")
        copied_strong.decompose()
        evidence = clean_text(line_copy.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or name in seen_names:
            raise RuntimeError(f"人物姓名、职务异常或姓名重复：{name}")
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
