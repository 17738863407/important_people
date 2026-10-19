from __future__ import annotations

import re
import ssl
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0972",
    "page_type": "人物表格页",
    "structure_group": "haikou_city_management_nested_person_tables",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".smfw_main .Custom_UnionStyle > table",
    "name_selector": "各内层表格精确姓名标签的相邻值单元格",
    "duty_selector": "各内层表格精确职务标签的相邻值单元格",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导班子及分工",
        "end_anchor": "扫码浏览",
        "include_selectors": [".smfw_main .Custom_UnionStyle > table"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "站点requests响应缺正文，原始HTTP含四个嵌套人物表格；首表姓名字段与头像文件名及简介姓名不一致，按强结构姓名职务字段原样输出",
    "confidence": "medium_web_source_conflict",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or "")).strip()


def fetch_complete_page(url: str) -> str:
    """通过站点可稳定返回正文的原始HTTP通道读取当前规则入口。"""
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        response = urlopen(request, timeout=30)
    except URLError as error:
        if not isinstance(error.reason, ssl.SSLCertVerificationError):
            raise
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        response = urlopen(request, timeout=30, context=ssl_context)
    with response:
        encoding = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(encoding, errors="replace")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(fetch_complete_page(final_url), "html.parser")
    rows: list[dict[str, str]] = []
    for table in soup.select(".smfw_main .Custom_UnionStyle > table"):
        fields: dict[str, str] = {}
        for table_row in table.select("tr"):
            cells = table_row.find_all(["th", "td"], recursive=False)
            for index, cell in enumerate(cells[:-1]):
                label = clean_text(cell.get_text(" ", strip=True))
                if label not in {"姓名", "职务"}:
                    continue
                fields[label] = clean_text(cells[index + 1].get_text(" ", strip=True))
        name = fields.get("姓名", "")
        duty = fields.get("职务", "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,12}", name) or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": ".smfw_main内层人物表格姓名与职务精确标签相邻单元格",
            }
        )
    if not rows:
        raise ValueError("领导正文未发现同时含姓名与职务精确标签的内层人物表格")
    return rows


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
