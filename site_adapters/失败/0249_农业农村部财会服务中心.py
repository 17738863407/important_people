from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def clean_text(value: str) -> str:
    """压缩页面排版空白，不改变姓名语义。"""
    return re.sub(r"\s+", "", value or "")


def is_hidden(node: Tag) -> bool:
    """排除节点及祖先明确隐藏的备用 DOM。"""
    current: Tag | None = node
    while current is not None:
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        style = re.sub(r"\s+", "", str(current.get("style", "")).lower())
        if "display:none" in style or "visibility:hidden" in style:
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """提取“领导班子”模块中的可见姓名；页面无逐人职务时依据留空。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one("div.finance_mechanism")
    if region is None:
        raise RuntimeError("未找到机构介绍区域")

    headings = [
        clean_text(node.get_text(" ", strip=True))
        for node in region.select("ul.lead_ul span")
        if not is_hidden(node)
    ]
    if "领导班子" not in headings:
        raise RuntimeError("机构介绍区域未显示“领导班子”分组")

    records: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for node in region.select("div.mechanism_box > p, div.mechanism_box > span"):
        if is_hidden(node):
            continue
        name = clean_text(node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": "",
                "confidence": "high",
                "parser": "page_inline_ckzx_leadership_names_v1",
            }
        )
    return records


PAGE_RULE = {
    "rule_id": "0249",
    "page_type": "人物列表完整页",
    "structure_group": "ckzx_leadership_name_box",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_ckzx_leadership_names_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "div.finance_mechanism div.mechanism_box",
    "name_selector": ":scope > p, :scope > span",
    "duty_selector": "",
    "detail_link_selector": "",
    "risk_flag": "页面仅列领导班子姓名，未提供逐人职务或独立详情页；依据说明须留空",
    "confidence": "high",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
