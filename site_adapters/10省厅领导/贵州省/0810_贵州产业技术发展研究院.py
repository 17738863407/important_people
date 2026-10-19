from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag


def clean_text(value: str) -> str:
    """压缩详情表格中的排版空白，不改变字段语义。"""
    text = " ".join((value or "").replace("\u3000", " ").replace("\xa0", " ").split())
    text = re.sub(r"\s+([，。；：、（）])", r"\1", text)
    return re.sub(r"([，。；：、（）])\s+", r"\1", text)


def clean_name(value: str) -> str:
    """移除姓名字符间的纯排版空格。"""
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


def same_origin(reference_url: str, candidate_url: str) -> bool:
    reference = urlsplit(reference_url)
    candidate = urlsplit(candidate_url)
    return (reference.scheme, reference.netloc) == (candidate.scheme, candidate.netloc)


def extract_profile_fields(detail_soup: BeautifulSoup) -> dict[str, str]:
    """按表头读取领导姓名与担任职务，忽略工作分工。"""
    fields: dict[str, str] = {}
    for row in detail_soup.select(".xldr_profile .profile_right table tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        label = re.sub(r"[\s\u2000-\u200a\u3000]+", "", cells[0].get_text(" ", strip=True))
        label = label.rstrip("：:")
        if label in {"姓名", "担任职务"}:
            fields[label] = clean_text(cells[1].get_text(" ", strip=True))
    return fields


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导目录顺序逐页校验详情表格并提取担任职务。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "lxml")
    directory = soup.select_one("ul#Left_Nav.navList")
    if directory is None:
        raise RuntimeError("未找到领导之窗目录")

    records: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for anchor in directory.select(":scope > li > a[href]"):
        if is_hidden(anchor):
            continue
        directory_name = clean_name(anchor.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", directory_name) or directory_name in seen_names:
            continue
        detail_url = urljoin(final_url, str(anchor.get("href", "")))
        detail_path = urlsplit(detail_url).path
        if not same_origin(final_url, detail_url) or not re.fullmatch(
            r"/xxgk/ldzc_5979379/\d{6}/t\d{8}_\d+\.html",
            detail_path,
        ):
            raise RuntimeError(f"{directory_name}详情路径不符合领导栏目结构")

        fetch_result = fetch_by_raw_requests(detail_url, timeout=30)
        fields = extract_profile_fields(BeautifulSoup(fetch_result.html, "lxml"))
        detail_name = clean_name(fields.get("姓名", ""))
        duty = fields.get("担任职务", "")
        if detail_name != directory_name:
            raise RuntimeError(f"目录姓名与详情表格不一致：{directory_name}/{detail_name or '空'}")
        if not duty:
            raise RuntimeError(f"{directory_name}详情表格缺少担任职务")

        seen_names.add(directory_name)
        records.append(
            {
                "name": directory_name,
                "duty": duty,
                "detail_url": fetch_result.final_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_gziid_leader_profiles_v1",
            }
        )
    return records


PAGE_RULE = {
    "rule_id": "0810",
    "page_type": "人物目录详情页",
    "structure_group": "gziid_leader_directory_profiles",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_gziid_leader_profiles_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "ul#Left_Nav.navList",
    "name_selector": ":scope > li > a[href]",
    "duty_selector": ".xldr_profile .profile_right table tr",
    "detail_link_selector": ":scope > li > a[href]",
    "risk_flag": "原脚本误标无效页；详情表格同时含担任职务与工作分工，只取前者",
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
