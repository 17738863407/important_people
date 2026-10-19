from __future__ import annotations

import ast
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
    "rule_id": "2229",
    "page_type": "人物目录详情页",
    "structure_group": "hangzhou_emergency_unitbuild_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "hangzhou_emergency_unitbuild_detail_v1",
    "leader_region_selector": "入口页unitbuild返回的领导信息目录",
    "name_selector": "a[href][title]",
    "duty_selector": "详情表格现任职务标签同行值",
    "detail_link_selector": "a[href][title]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_unitbuild_directory",
        "same_host_only": True,
        "detail_name_selector": "详情人物标题与首行姓名",
        "detail_duty_selector": "现任职务标签同行值",
    },
    "risk_flag": "入口领导目录由unitbuild接口注入，详情含工作分工和长简历，仅取现任职务强字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip()


def extract_detail_fields(html: str) -> tuple[str, str]:
    """从详情表格姓名行和现任职务标签同行提取强字段。"""
    soup = BeautifulSoup(html, "html.parser")
    name = ""
    duty = ""
    for row in soup.select("table tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if not cells:
            continue
        texts = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]
        if len(cells) >= 2 and compact_text(texts[0]).rstrip("：:") == "现任职务":
            duty = texts[1]
        elif len(cells) >= 2 and not name:
            candidate = compact_text(texts[0])
            if re.fullmatch(r"[\u3400-\u9fff·]{2,8}", candidate):
                name = candidate
    if not name and soup.title:
        name = compact_text(soup.title.get_text(" ", strip=True))
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按unitbuild目录原序逐页核验现任职务。"""
    soup = BeautifulSoup(html, "html.parser")
    script = soup.select_one("script[src*='unitbuild'][url][querydata]")
    if script is None:
        raise ValueError("入口页未声明领导信息unitbuild接口")
    query_data = ast.literal_eval(str(script.get("querydata", "")))
    if not isinstance(query_data, dict):
        raise ValueError("unitbuild查询参数不是字典")
    host = urlparse(final_url).netloc.lower()
    api_url = urljoin(final_url, str(script.get("url", "")))
    if urlparse(api_url).netloc.lower() != host:
        raise ValueError("unitbuild接口不属于入口站点")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": final_url})
    response = session.get(api_url, params=query_data, timeout=30)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    unit_html = data.get("html", "") if isinstance(data, dict) else ""
    if not unit_html:
        raise ValueError("unitbuild接口未返回领导信息目录HTML")

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in BeautifulSoup(str(unit_html), "html.parser").select("a[href][title]"):
        href = str(anchor.get("href", "")).strip()
        name = compact_text(anchor.get("title", "") or anchor.get_text(" ", strip=True))
        if href.startswith("#") or not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, href)
        if urlparse(detail_url).netloc.lower() != host:
            continue
        detail_response = session.get(detail_url, timeout=30)
        detail_response.raise_for_status()
        detail_response.encoding = detail_response.apparent_encoding or "utf-8"
        detail_name, duty = extract_detail_fields(detail_response.text)
        if detail_name != name or not duty:
            raise ValueError(f"详情页姓名或现任职务不匹配：{detail_url}")
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "selector_summary": "入口unitbuild领导目录DOM原序；详情表格现任职务标签同行值",
            }
        )
    if not records:
        raise ValueError("未在应急管理局领导目录及详情页中解析到有效人物")
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
