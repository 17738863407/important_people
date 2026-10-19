from __future__ import annotations

import html as html_lib
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """压缩网页字段中的排版空白。"""
    text = re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()
    text = re.sub(r"\s+([，。、；：（）])", r"\1", text)
    return re.sub(r"([，、])\s+", r"\1", text)


def clean_name(value: str) -> str:
    """去除姓名内部的排版空白。"""
    return clean_text(value).replace(" ", "")


def extract_detail(detail_html: str) -> tuple[str, str]:
    """从详情信息表格提取姓名与职务字段。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    table = soup.select_one(".ld_fg table") or soup.select_one("table")
    text = clean_text(table.get_text(" ", strip=True) if table else "")
    match = re.search(
        r"姓\s*名[:：]\s*(?P<name>.+?)\s*职\s*务[:：]\s*(?P<duty>.+?)\s*出生年月[:：]",
        text,
    )
    if not match:
        return "", ""
    return clean_name(match.group("name")), clean_text(match.group("duty"))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析入口内联目录脚本，并在线读取每个详情信息表格。"""
    import requests

    soup = BeautifulSoup(html, "html.parser")
    menu_script = next((node for node in soup.find_all("script") if node.string and "#ldlist" in node.string), None)
    script_text = str(menu_script.string or "") if menu_script else ""
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, segment in enumerate(re.split(r"(?=var\s+src\s*=)", script_text), start=1):
        url_match = re.search(r'var\s+src\s*=\s*"(?P<detail>https?://[^"]+)"', segment)
        name_match = re.search(r"<p>(?P<name>[^<]+)</p>", segment)
        if not url_match or not name_match:
            continue
        listed_name = clean_name(html_lib.unescape(name_match.group("name")))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", listed_name) or listed_name in seen:
            continue
        response = session.get(url_match.group("detail"), timeout=30, verify=False)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        name, duty = extract_detail(response.text)
        if name != listed_name:
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
                "parser": "page_inline_guizhou_wsb_online_details_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2966",
    "page_type": "多人物详情合并页",
    "structure_group": "贵州外事办内联目录转详情表格",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_guizhou_wsb_online_details_v2",
    "leader_region_selector": "生成#ldlist的内联script",
    "name_selector": "内联目录卡片p字段",
    "duty_selector": "详情.ld_fg table职务字段",
    "detail_link_selector": "内联目录var src字段",
    "detail_strategy": {
        "required": True,
        "mode": "custom_online_detail",
        "detail_collector_type": "requests",
    },
    "risk_flag": "入口原始DOM无人物li，需解析当前内联目录脚本；姓名含排版空格并与详情表格交叉校验",
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
