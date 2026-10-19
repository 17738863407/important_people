from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4412",
    "page_type": "领导信息左右配对卡片页",
    "structure_group": "qh_procuratorate_leader_rows_v1",
    "reuse_scope": "same_verified_template",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "page_inline_qh_procuratorate_leader_rows_v1",
    "leader_region_selector": ".mol_contents",
    "name_selector": ".mol_contents_row .mol_contents_L > span",
    "duty_selector": ".mol_contents_row .mol_contents_L",
    "detail_link_selector": ".mol_contents_row .mol_contents_r a.btnMore[href]",
    "detail_strategy": {"required": False, "mode": "paired_row_link"},
    "risk_flag": "右侧简介含履历，仅以左侧强结构提取姓名和原始职务；右侧只取同一行独立详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """清理网页排版空白，不改写原始职务语义。"""
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def _is_hidden(node: Tag) -> bool:
    """排除节点及领导行祖先上的明确隐藏标记。"""
    for current in (node, *node.parents):
        if not isinstance(current, Tag):
            continue
        style = re.sub(r"\s+", "", str(current.get("style", "")).lower())
        classes = {str(item).lower() for item in (current.get("class") or [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "hidden" in classes:
            return True
    return False


def _duty_before_name(left: Tag, name_node: Tag) -> str:
    """读取姓名 span 之前的左侧文本，避免姓名内部排版空格影响边界。"""
    parts: list[str] = []
    for child in left.contents:
        if child is name_node:
            break
        if isinstance(child, Tag):
            parts.append(child.get_text(" ", strip=True))
        else:
            parts.append(str(child))
    return _clean_text(" ".join(parts)).strip(" ：:，,；;")


def _detail_url(row: Tag, final_url: str) -> str:
    """只接受当前领导行右侧“更多”所指向的同站 HTTP(S) 详情页。"""
    link = row.select_one(".mol_contents_r a.btnMore[href]")
    if link is None or _is_hidden(link):
        return ""
    href = str(link.get("href", "")).strip()
    if not href or href.startswith(("#", "javascript:", "mailto:")):
        return ""
    resolved = urljoin(final_url, href)
    parsed = urlparse(resolved)
    base = urlparse(final_url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc != base.netloc or resolved == final_url:
        return ""
    return resolved


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按页面 DOM 顺序解析左侧职务姓名，并配对右侧独立详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".mol_contents")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in region.select(":scope > .mol_contents_row"):
        left = row.select_one(":scope > .mol_contents_L")
        name_node = left.select_one(":scope > span") if left is not None else None
        if left is None or name_node is None or _is_hidden(row):
            continue

        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None:
            continue

        duty = _duty_before_name(left, name_node)
        if not duty:
            continue

        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": _detail_url(row, final_url),
                "source_text": _clean_text(left.get_text(" ", strip=True)),
                "method": page_rule["parser"],
                "note": "strategy=paired_leader_row；scope=.mol_contents；order=row_dom",
            }
        )
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
