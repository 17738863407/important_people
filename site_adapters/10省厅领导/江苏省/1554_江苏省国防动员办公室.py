from __future__ import annotations

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
    "rule_id": "1554",
    "page_type": "领导成员内嵌数据页",
    "structure_group": "jiangsu_jpage_embedded_records_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML内嵌XML",
    "fetch_mode": "raw_http",
    "extract_mode": "field_pair",
    "collector": "requests",
    "parser": "inline_parse_page",
    "leader_region_selector": "[id='434766'] > script[type='text/xml']",
    "name_selector": ".main_right_brief_span1 span:not(.zw)",
    "duty_selector": ".main_right_brief_span1 .zw",
    "detail_link_selector": "",
    "content_scope": {
        "include_selectors": ["[id='434766'] > script[type='text/xml']"],
        "exclude_selectors": ["span[style*='display:none']", "div[style*='display:none']"],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物记录位于内嵌XML的CDATA中，只取标题行姓名和职务，排除隐藏简介、分工与图片",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def normalize_text(value: str) -> str:
    """只压缩页面排版空白。"""
    return " ".join((value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按内嵌XML记录顺序解析领导成员标题行。"""
    del final_url, page_rule
    soup = BeautifulSoup(html, "html.parser")
    data_script = soup.select_one("[id='434766'] > script[type='text/xml']")
    if data_script is None:
        raise ValueError("未找到领导成员内嵌XML数据")
    data_text = data_script.get_text("", strip=False)
    fragments = re.findall(r"<record>\s*<!\[CDATA\[(.*?)\]\]>\s*</record>", data_text, flags=re.DOTALL)
    if not fragments:
        raise ValueError("领导成员内嵌XML中未发现记录")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for fragment in fragments:
        item = BeautifulSoup(fragment, "html.parser")
        title_line = item.select_one(".main_right_brief_span1")
        duty_node = title_line.select_one(".zw") if title_line else None
        if title_line is None or duty_node is None:
            raise ValueError("领导成员记录缺少标题行或职务节点")
        name_node = next(
            (node for node in title_line.select("span") if "zw" not in (node.get("class") or [])),
            None,
        )
        name = re.sub(r"\s+", "", normalize_text(name_node.get_text(" ", strip=True) if name_node else ""))
        duty = normalize_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or not duty:
            raise ValueError(f"领导成员记录姓名或职务异常：姓名={name!r}，职务={duty!r}")
        if name in seen_names:
            raise ValueError(f"领导成员记录出现重复姓名：{name}")
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
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
