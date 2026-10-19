from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3070",
    "page_type": "领导职务名单正文页",
    "structure_group": "xiaolangdi_visible_leader_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "Chrome渲染DOM",
    "fetch_mode": "chrome",
    "extract_mode": "field_pair",
    "collector": "chrome_cdp",
    "parser": "inline_parse_page",
    "leader_region_selector": ".article-detail",
    "name_selector": ".article-detail p.MsoNormal",
    "duty_selector": ".article-detail p.MsoNormal",
    "detail_link_selector": "",
    "content_scope": {
        "include_selectors": [".article-detail > p.MsoNormal"],
        "exclude_selectors": ["[hidden]", "[aria-hidden='true']", "[style*='display:none']"],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "2026-08-24复核时HTTPS被远端关闭连接、HTTP持续超时；页面恢复后仍只解析当前可见.article-detail p.MsoNormal领导行，不使用搜索摘要或历史名单",
    "confidence": "failed",
    "filter_policy": "strong_no_wordlist",
}


def is_hidden(node: Tag) -> bool:
    """排除当前节点或祖先明确隐藏的DOM。"""
    current: Tag | None = node
    while current is not None:
        if current.has_attr("hidden") or str(current.get("aria-hidden") or "").lower() == "true":
            return True
        style = re.sub(r"\s+", "", str(current.get("style") or "").lower())
        if "display:none" in style or "visibility:hidden" in style:
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按当前可见正文段落顺序解析“职务：姓名”领导行。"""
    del final_url, page_rule
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".article-detail")
    if region is None:
        raise ValueError("未找到小浪底管理中心领导正文")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in region.select("p.MsoNormal"):
        if is_hidden(paragraph):
            continue
        line = re.sub(r"\s+", "", paragraph.get_text("", strip=True))
        parts = re.split(r"[：:]", line, maxsplit=1)
        if len(parts) != 2:
            continue
        duty, name = parts
        if not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            continue
        if name in seen_names:
            raise ValueError(f"领导正文出现重复姓名：{name}")
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
            }
        )
    if not rows:
        raise ValueError("领导正文未解析到当前可见人物行")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
