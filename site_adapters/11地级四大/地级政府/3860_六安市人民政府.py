from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析主页面引用的官方市长、副市长栏目脚本。"""
    del html, final_url
    source = str(page_rule.get("url", ""))
    session = requests.Session()
    session.trust_env = False
    headers = {"User-Agent": "Mozilla/5.0", "Referer": source}
    response = session.get(source, headers=headers, timeout=25)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, "html.parser")
    rows: list[dict[str, str]] = []
    for group in soup.select("#szf-ledcont-szfld > div"):
        duty_node = group.select_one(".ld-zw")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        script_node = group.select_one(".ld-xx script[src]")
        if not duty or script_node is None:
            continue
        script_url = urljoin(response.url, str(script_node.get("src", "")))
        script_response = session.get(script_url, headers=headers, timeout=25)
        script_response.raise_for_status()
        script_response.encoding = script_response.apparent_encoding or script_response.encoding
        fragments = re.findall(
            r"var\s+linkLi\s*=\s*'(?P<html>.*?)';",
            script_response.text,
            flags=re.DOTALL,
        )
        for fragment in fragments:
            anchor = BeautifulSoup(fragment, "html.parser").select_one("li > a[href]")
            if anchor is None:
                continue
            name_node = anchor.select_one(".img-title")
            name = clean_text(
                name_node.get_text(" ", strip=True) if name_node else ""
            ).replace(" ", "")
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                rows.append(
                    {
                        "name": name,
                        "duty": "",
                        "evidence": duty,
                        "detail_url": urljoin(response.url, str(anchor.get("href") or "")),
                        "confidence": "high",
                        "parser": "page_inline_luan_external_list_scripts_v2",
                    }
                )
    return rows


PAGE_RULE = {"rule_id": "3860", "page_type": "外部栏目脚本领导卡片", "load_mode": "静态HTML引用外部栏目脚本",
             "fetch_mode": "online", "inline_parser_handles_fetch": True,
             "inline_fetch_collector": "requests", "extract_mode": "grouped_list",
             "parser": "page_inline_luan_external_list_scripts_v2", "leader_region_selector": "#szf-ledcont-szfld",
             "name_selector": ".ld-xx .img-title", "duty_selector": ".ld-zw",
             "detail_link_selector": ".ld-xx li > a[href]", "locator_strategy": "custom_parse_page",
             "risk_flag": "人物卡片由外部JavaScript写入", "confidence": "high"}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__": main()
