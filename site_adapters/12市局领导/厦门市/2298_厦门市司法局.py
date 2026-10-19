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
    "rule_id": "2298",
    "page_type": "多人物详情合并页",
    "structure_group": "xm_justice_leader_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_justice_leader_cards_v2",
    "leader_region_selector": ".ldzc_con",
    "name_selector": ".ldzc_tit",
    "duty_selector": ".ldzc_r p:first-of-type",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "历史版本硬编码人物结果；现按卡片DOM顺序提取标题姓名和首个明确职务段落，并用简介段落校验姓名",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def clean_name(value: str) -> str:
    """移除姓名节点中的版式空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物卡片顺序提取标题姓名和首段原始职务。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.select(page_rule["leader_region_selector"])
    if not blocks:
        raise RuntimeError("未找到司法局领导人物卡片")
    records: list[object] = []
    seen: set[str] = set()
    for block in blocks:
        name_node = block.select_one(page_rule["name_selector"])
        paragraphs = block.select(".ldzc_r p")
        if name_node is None or len(paragraphs) < 3:
            raise RuntimeError("人物卡片缺少姓名、职务或简介字段")
        name = clean_name(name_node.get_text(" ", strip=True))
        evidence = clean_text(paragraphs[0].get_text(" ", strip=True))
        biography = clean_name(paragraphs[-1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not biography.startswith(name + "，"):
            raise RuntimeError(f"人物标题与简介姓名不一致：{name or '未知姓名'}")
        if not evidence or name in seen:
            raise RuntimeError(f"人物职务缺失或姓名重复：{name}")
        seen.add(name)
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
