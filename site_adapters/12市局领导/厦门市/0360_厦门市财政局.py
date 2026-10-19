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
    "rule_id": "0360",
    "page_type": "多人物详情合并页",
    "structure_group": "xm_finance_inner_tabs_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_finance_inner_tabs_profiles_v2",
    "leader_region_selector": ".tabs_inner",
    "name_selector": ".tabs_header li a",
    "duty_selector": ".tabs_content .list_ldfg",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同页存在多组选项卡且人物块含分工；选择含list_ldfg的内层选项卡并只取简介现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def clean_name(value: str) -> str:
    """清除姓名节点中的排版空白。"""
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物选项卡标题顺序配对人物块并提取完整现任句。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = next(
        (node for node in soup.select(".tabs_inner") if node.select(".list_ldfg")),
        None,
    )
    if region is None:
        return []
    names = [
        clean_name(node.get_text(" ", strip=True))
        for node in region.select(".tabs_header li a")
    ]
    blocks = region.select(".tabs_content .list_ldfg")
    if not names or len(names) != len(blocks):
        raise RuntimeError(f"人物选项卡与内容块数量不一致：{len(names)} != {len(blocks)}")

    records: list[object] = []
    seen: set[str] = set()
    for name, block in zip(names, blocks, strict=True):
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
            raise RuntimeError(f"人物姓名异常或重复：{name}")
        block_text = clean_text(block.get_text(" ", strip=True))
        evidence_match = re.search(r"现任[^。]*。", block_text)
        if name not in block_text or evidence_match is None:
            raise RuntimeError(f"人物块无法核对姓名或现任句：{name}")
        evidence = re.sub(r"^现任\s*", "", evidence_match.group(0)).removesuffix("。").strip()
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
