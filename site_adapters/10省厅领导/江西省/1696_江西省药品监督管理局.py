from __future__ import annotations

import json
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


PAGE_RULE = {
    "rule_id": "1696",
    "domain": "mpa.jiangxi.gov.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "jiangxi_mpa_inline_render_payload_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "动态HTML载荷",
    "fetch_mode": "raw_http",
    "extract_mode": "inline_payload_direct",
    "collector": "raw_http",
    "parser": "page_inline_jiangxi_mpa_render_payload_profiles_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面DOM人物区由脚本渲染；原始响应内嵌JSON content为权威载荷；站内验证码字样会误触发浏览器",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def extract_rendered_content(html: str) -> str:
    """动态解码页面脚本内包含领导标题块的JSON content载荷。"""
    decoder = json.JSONDecoder()
    pattern = re.compile(r"const\s+[A-Za-z0-9_]+\s*=\s*\[\{\s*content\s*:\s*")
    for match in pattern.finditer(html):
        payload = html[match.end() :].lstrip()
        try:
            content_data, _ = decoder.raw_decode(payload)
        except json.JSONDecodeError:
            continue
        if not isinstance(content_data, dict):
            continue
        content = str(content_data.get("content", ""))
        if "ld_conr_title" in content:
            return content
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按渲染载荷中的人物标题块顺序提取姓名和职务。"""
    content = extract_rendered_content(html)
    if not content:
        return []
    soup = BeautifulSoup(content, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for title in soup.select(".ld_conr_title"):
        name_node = title.select_one("span#myLeadName")
        duty_node = title.select_one("span.job")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True)))
        duty = clean_text(duty_node.get_text(" ", strip=True)).strip(" ：:，,；;。 ")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；source=inline-JSON-content-payload；"
                    "item=.ld_conr_title；name=span#myLeadName；duty=span.job"
                ),
            }
        )

    return records


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
