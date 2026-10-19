from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2610", "page_type": "人物列表完整页", "structure_group": "sjz_commerce_duty_name_colon_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_commerce_duty_name_colon_v2",
    "leader_region_selector": "#conN p", "name_selector": "冒号前首文本节点末尾2至4字姓名",
    "duty_selector": "冒号前姓名之前的完整原文", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "职务与姓名无空白连接；冒号后为主持、分管或协助职责；末段为A/B角制度说明",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅合并网页排版空白，不改变原始职务语义。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def split_duty_and_name(title: str) -> tuple[str, str]:
    """用通用职务结尾边界唯一确定末尾姓名，不保存固定人物或职务列表。"""
    compact = re.sub(r"\s+", "", title).rstrip("：:")
    candidates: list[tuple[str, str]] = []
    for name_length in range(2, 5):
        if len(compact) <= name_length:
            continue
        duty = compact[:-name_length]
        name = compact[-name_length:]
        if re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) and duty.endswith(("员", "长", "官", "书记", "成员")):
            candidates.append((duty, name))
    if len(candidates) != 1:
        raise RuntimeError(f"职务姓名边界候选数量异常：{title} -> {len(candidates)}")
    return candidates[0]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析每个工作分工段落冒号前的完整职务与姓名，排除冒号后职责。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#conN")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")
    paragraphs = regions[0].select("p")
    if not paragraphs:
        raise RuntimeError("领导正文没有工作分工段落")

    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in paragraphs:
        text_nodes = [clean_text(str(node)) for node in paragraph.descendants if isinstance(node, NavigableString) and clean_text(str(node))]
        if not text_nodes or not text_nodes[0].endswith(("：", ":")):
            continue
        evidence, name = split_duty_and_name(text_nodes[0])
        responsibility = clean_text(" ".join(text_nodes[1:]))
        if not evidence or name in seen_names:
            raise RuntimeError(f"人物职务为空或姓名重复：{name}")
        if not responsibility.startswith(("主持", "分管", "协助")):
            raise RuntimeError(f"人物职责字段边界异常：{name} {responsibility}")
        if paragraph.select_one("a[href]") is not None:
            raise RuntimeError(f"人物段落出现未审计链接：{name}")

        seen_names.add(name)
        records.append(PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"],
        ))
    if not records:
        raise RuntimeError("工作分工段落没有可验证人物")
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
