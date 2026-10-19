from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2694",
    "page_type": "人物目录详情页",
    "structure_group": "hangzhou_transport_responsible_people_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "hangzhou_transport_responsible_people_detail_v1",
    "leader_region_selector": "标题为本机关负责人的.zfxxgk_item",
    "name_selector": ".zfxxgk_zdgkc li a[href]",
    "duty_selector": "详情表格职务标签后的单元格",
    "detail_link_selector": ".zfxxgk_zdgkc li a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_group_links",
        "same_host_only": True,
        "detail_name_selector": "领导姓名标签后的单元格",
        "detail_duty_selector": "职务标签后的单元格",
    },
    "risk_flag": "同页含内设机构和直属单位，必须先锁定本机关负责人分组",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip()


def extract_labeled_fields(html: str) -> tuple[str, str]:
    """从详情表格标签后相邻单元格提取领导姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    fields: dict[str, str] = {}
    for row in soup.select("table tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        texts = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]
        for index, text in enumerate(texts[:-1]):
            label = compact_text(text).rstrip("：:")
            if label in {"领导姓名", "职务"}:
                fields[label] = texts[index + 1]
    return compact_text(fields.get("领导姓名", "")), fields.get("职务", "")


def find_people_region(soup: BeautifulSoup) -> BeautifulSoup:
    for item in soup.select(".zfxxgk_item"):
        heading = item.select_one(".zfxxgk_zdgktit")
        if heading and compact_text(heading.get_text(" ", strip=True)) == "本机关负责人":
            return item
    raise ValueError("未找到本机关负责人分组")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按本机关负责人表格版面原序逐页核验姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = find_people_region(soup)
    host = urlparse(final_url).netloc.lower()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": final_url})
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in region.select(".zfxxgk_zdgkc li a[href]"):
        name = compact_text(anchor.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, anchor.get("href", ""))
        if urlparse(detail_url).netloc.lower() != host:
            continue
        response = session.get(detail_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        detail_name, duty = extract_labeled_fields(response.text)
        if detail_name != name or not duty:
            raise ValueError(f"详情页姓名或职务字段不匹配：{detail_url}")
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "selector_summary": "本机关负责人分组表格版面原序；详情领导姓名与职务标签字段",
            }
        )
    if not records:
        raise ValueError("未在交通运输局本机关负责人分组及详情页中解析到有效人物")
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
