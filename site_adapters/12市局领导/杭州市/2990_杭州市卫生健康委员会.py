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
    "rule_id": "2990",
    "page_type": "人物目录详情页",
    "structure_group": "hangzhou_health_unitbuild_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "hangzhou_health_unitbuild_detail_v1",
    "leader_region_selector": "入口页unitbuild返回的本机关负责人目录",
    "name_selector": "unitbuild目录li > a[href][title]",
    "duty_selector": "详情页.bt_content中职务标签后的段落",
    "detail_link_selector": "unitbuild目录li > a[href][title]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_unitbuild_directory",
        "same_host_only": True,
        "detail_name_selector": "详情页title与#now",
        "detail_duty_selector": ".bt_content strong职务标签后的p",
    },
    "risk_flag": "详情页同时含工作分工、简历和电话，仅提取职务标签对应的强字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def compact_text(value: str) -> str:
    """清除页面排版空白，不改变职务文字和标点。"""
    text = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", value or "")
    return re.sub(r"\s+", "", text).strip()


def extract_detail_fields(html: str) -> tuple[str, str]:
    """从详情标题及“职务”标签后的独立段落读取强字段。"""
    soup = BeautifulSoup(html, "html.parser")
    title_name = compact_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    heading = soup.select_one("#now")
    heading_name = compact_text(heading.get_text(" ", strip=True).split("\n", 1)[0]) if heading else ""
    name = heading_name or title_name
    if title_name and heading_name and title_name != heading_name:
        raise ValueError("详情页标题与人物标题不一致")

    content = soup.select_one(".bt_content")
    if content is None:
        raise ValueError("详情页缺少人物内容区域")
    duty = ""
    for label in content.find_all("strong"):
        if compact_text(label.get_text(" ", strip=True)).rstrip("：:") != "职务":
            continue
        value_node = label.find_next_sibling("p")
        if value_node is not None:
            duty = compact_text(value_node.get_text(" ", strip=True))
        break
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """动态读取unitbuild目录，并按入口DOM顺序核验每个详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    script = soup.select_one("script[src*='unitbuild'][url][querydata]")
    if script is None:
        raise ValueError("入口页未声明负责人unitbuild接口")
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
        raise ValueError("unitbuild接口未返回负责人目录HTML")

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    unit_soup = BeautifulSoup(str(unit_html), "html.parser")
    for anchor in unit_soup.select(".page-content li > a[href][title]"):
        name = compact_text(anchor.get("title", "") or anchor.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, str(anchor.get("href", "")))
        if urlparse(detail_url).netloc.lower() != host or detail_url == final_url:
            continue

        detail_response = session.get(detail_url, timeout=30)
        detail_response.raise_for_status()
        detail_response.encoding = detail_response.apparent_encoding or "utf-8"
        detail_name, duty = extract_detail_fields(detail_response.text)
        if detail_name != name or not duty:
            raise ValueError(f"详情页姓名或职务字段不匹配：{detail_url}")
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "selector_summary": "入口unitbuild目录DOM原序；详情页职务标签后的独立段落",
            }
        )
    if not records:
        raise ValueError("未在负责人目录及详情页中解析到有效人物")
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
