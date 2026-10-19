from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1029",
    "page_type": "人物列表完整页",
    "structure_group": "hubaogy_about_es_module_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "raw_http",
    "extract_mode": "javascript_module_data",
    "collector": "static_http_js_module",
    "parser": "page_inline_hubaogy_about_module_v1",
    "leader_region_selector": 'script[type="module"][src]',
    "name_selector": "ABOUT001.data[].b",
    "duty_selector": "ABOUT001.data[].c",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "入口为Vue空壳；从当前入口动态发现主模块及about哈希模块，只解析ABOUT001领导数组",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def decode_js_string(value: str) -> str:
    """解码JavaScript模块中的JSON兼容字符串转义。"""
    return str(json.loads(f'"{value}"')).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """动态发现当前about模块，并按模块内领导数组原始顺序抽取。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    entry_script = soup.select_one('script[type="module"][src]')
    if entry_script is None:
        raise RuntimeError("入口HTML未发现ES主模块")

    entry_script_url = urljoin(final_url, str(entry_script.get("src") or ""))
    entry_result = fetch_html_with_strategy(entry_script_url, "raw_http")
    route_match = re.search(r'["\'](?:\./)?(?P<path>about\.[0-9a-f]+\.js)["\']', entry_result.html)
    if route_match is None:
        raise RuntimeError("主模块未发现当前about哈希模块")

    about_module_url = urljoin(entry_result.final_url, route_match.group("path"))
    about_js = fetch_html_with_strategy(about_module_url, "raw_http").html
    leadership_match = re.search(
        r'id:"ABOUT001",data:\[(?P<data>.*?)\]\}\s*,\{name:',
        about_js,
        flags=re.DOTALL,
    )
    if leadership_match is None:
        raise RuntimeError("about模块未发现ABOUT001领导数组")

    person_pattern = re.compile(
        r'\{a:"(?:\\.|[^"])*",b:"(?P<name>(?:\\.|[^"])*)",'
        r'c:"(?P<duty>(?:\\.|[^"])*)",d:',
        flags=re.DOTALL,
    )
    rows: list[dict[str, str]] = []
    for match in person_pattern.finditer(leadership_match.group("data")):
        name = decode_js_string(match.group("name"))
        duty = decode_js_string(match.group("duty"))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": str(page_rule.get("parser") or ""),
                "selector_summary": "entry=ES主模块；route=about哈希模块；data=ABOUT001.data[].b+c",
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
