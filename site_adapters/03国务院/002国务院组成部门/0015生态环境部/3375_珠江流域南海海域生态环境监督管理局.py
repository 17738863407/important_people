from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag


def clean_text(value: str) -> str:
    """清理详情字段中的排版空白，不改变原文语义。"""
    text = " ".join((value or "").replace("\u3000", " ").replace("\xa0", " ").split())
    text = re.sub(r"\s+([，。；：、（）])", r"\1", text)
    return re.sub(r"([，。；：、（）])\s+", r"\1", text)


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
    """按领导之窗目录顺序逐页校验姓名并提取当前职务。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "lxml")
    directory = soup.select_one("dl.active.leaders")
    if directory is None:
        raise RuntimeError("未找到领导之窗目录")

    source_url = str(page_rule["url"])
    leader_root = urljoin(final_url, "../")
    records: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for anchor in directory.select(":scope > dd > a[href]"):
        if is_hidden(anchor):
            continue
        directory_name = clean_text(anchor.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", directory_name) or directory_name in seen_names:
            continue
        candidate_url = urljoin(final_url, str(anchor.get("href", "")))
        if not same_origin(final_url, candidate_url) or not candidate_url.startswith(leader_root):
            continue

        fetch_result = fetch_by_raw_requests(candidate_url, timeout=30)
        detail_soup = BeautifulSoup(fetch_result.html, "lxml")
        name_node = detail_soup.select_one(".jgznpage-rgt .person-info .name-info > b")
        duty_node = detail_soup.select_one(".jgznpage-rgt .person-info .descr.on .TRS_Editor")
        detail_name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").rstrip("。").strip()
        if detail_name != directory_name:
            raise RuntimeError(f"目录姓名与详情标题不一致：{directory_name}/{detail_name or '空'}")
        if not duty:
            raise RuntimeError(f"{directory_name}详情页未找到当前职务字段")

        seen_names.add(directory_name)
        detail_url = "" if candidate_url.rstrip("/") == source_url.rstrip("/") else fetch_result.final_url
        records.append(
            {
                "name": directory_name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_zjnh_leader_details_v1",
            }
        )
    return records


PAGE_RULE = {
    "rule_id": "3375",
    "page_type": "人物目录详情页",
    "structure_group": "zjnh_leader_directory_and_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_zjnh_leader_details_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "dl.active.leaders",
    "name_selector": ":scope > dd > a[href]",
    "duty_selector": ".jgznpage-rgt .person-info .descr.on .TRS_Editor",
    "detail_link_selector": ":scope > dd > a[href]",
    "risk_flag": "入口本身是首名领导详情页；必须按侧栏目录顺序逐页校验姓名，入口页不得重复写入详情链接",
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
