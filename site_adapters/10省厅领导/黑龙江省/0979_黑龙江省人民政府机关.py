from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag


def clean_text(value: str) -> str:
    """压缩卡片排版空白，不改变职务字段语义。"""
    return " ".join((value or "").replace("\xa0", " ").split()).strip()


def clean_name(value: str) -> str:
    """移除姓名字符间的全角或普通排版空格。"""
    return re.sub(r"[\s\u2000-\u200a\u3000]+", "", value or "")


def normalized_heading(value: str) -> str:
    """统一详情标题的空白与冒号，用于一一对应校验。"""
    return clean_name(value).replace(":", "：")


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


def same_origin(reference_url: str, candidate_url: str) -> bool:
    reference = urlsplit(reference_url)
    candidate = urlsplit(candidate_url)
    return (reference.scheme, reference.netloc) == (candidate.scheme, candidate.netloc)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析省政府机关领导卡片，并逐详情验证标题。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one("div.szfld.mt20")
    if region is None:
        raise RuntimeError("未找到省政府机关领导区域")
    heading = clean_text(region.select_one(".hd.common_hd").get_text(" ", strip=True))
    if heading != "省政府机关领导":
        raise RuntimeError(f"目标分组标题不一致：{heading or '空'}")

    records: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for anchor in region.select("ul.cont dd > a[href]"):
        if is_hidden(anchor):
            continue
        card_text = clean_text(anchor.get_text(" ", strip=True)).replace(":", "：")
        if "：" not in card_text:
            continue
        duty, raw_name = (part.strip() for part in card_text.split("：", 1))
        name = clean_name(raw_name)
        if not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or name in seen_names:
            continue

        detail_url = urljoin(final_url, str(anchor.get("href", "")))
        detail_path = urlsplit(detail_url).path
        if not same_origin(final_url, detail_url) or not re.fullmatch(
            r"/hlj/c108398/\d{6}/c00_\d+\.shtml",
            detail_path,
        ):
            raise RuntimeError(f"{name}详情路径不符合省政府机关栏目结构")

        fetch_result = fetch_by_raw_requests(detail_url, timeout=30)
        detail_soup = BeautifulSoup(fetch_result.html, "lxml")
        expected_heading = normalized_heading(f"{duty}：{name}")
        detail_headings = {
            normalized_heading(node.get_text(" ", strip=True))
            for node in detail_soup.select("h1")
            if not is_hidden(node)
        }
        if expected_heading not in detail_headings:
            raise RuntimeError(f"{name}详情标题与目录卡片不一致")

        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": fetch_result.final_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_hlj_government_office_cards_v1",
            }
        )
    return records


PAGE_RULE = {
    "rule_id": "0979",
    "page_type": "人物目录详情页",
    "structure_group": "hlj_government_office_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_hlj_government_office_cards_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "div.szfld.mt20",
    "name_selector": "ul.cont dd > a[href]",
    "duty_selector": "卡片冒号前字段",
    "detail_link_selector": "ul.cont dd > a[href]",
    "risk_flag": "页面下方含大量部门和市县链接；仅省政府机关领导分组可进入人物结果",
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
