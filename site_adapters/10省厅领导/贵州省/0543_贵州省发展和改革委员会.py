from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """压缩网页字段中的排版空白，不改变职务语义。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\u200b", "").split())


def clean_duty_evidence(value: str) -> str:
    """删除独立兼任状态标记，保留具体的兼任职务。"""
    return re.sub(r"(?:<\s*兼\s*>|[（(]\s*兼\s*[）)])", "", clean_text(value)).strip()


def extract_profile(html: str) -> tuple[str, str]:
    """从详情页姓名节点及页面职务变量提取强结构字段。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    name_node = soup.select_one(".ldjj_boxr_tit .ld_xm")
    name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")

    duty = ""
    title_region = soup.select_one(".ldjj_boxr_tit")
    if title_region:
        match = re.search(r'var\s+ld_zw\s*=\s*"([^"\\]*(?:\\.[^"\\]*)*)"', str(title_region))
        if match:
            duty = clean_duty_evidence(match.group(1).replace(r'\"', '"').replace(r"\/", "/"))
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口列表顺序在线请求人物详情并提取姓名、担任职务。"""
    import requests
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    links = soup.select(".ldjj_boxl_01c a[href], .ldjj_boxl_02c li a[href]")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, link in enumerate(links, start=1):
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not detail_url:
            continue
        response = session.get(detail_url, timeout=30, verify=False)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        name, duty = extract_profile(response.text)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": response.url,
                "source_order": str(source_order),
                "confidence": "high" if duty else "medium",
                "parser": "page_inline_guizhou_fgw_detail_fields_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "0543",
    "page_type": "人物列表完整页",
    "structure_group": "贵州省发改委领导列表转详情",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_guizhou_fgw_detail_fields_v2",
    "leader_region_selector": ".ldjj_boxl_01c, .ldjj_boxl_02c",
    "name_selector": ".ldjj_boxr_tit .ld_xm",
    "duty_selector": ".ldjj_boxr_tit script中的ld_zw变量",
    "detail_link_selector": ".ldjj_boxl_01c a[href], .ldjj_boxl_02c li a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "custom_online_detail",
        "detail_collector_type": "requests",
    },
    "risk_flag": "详情职务由脚本变量生成，需直接解析对应人物页的ld_zw字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
