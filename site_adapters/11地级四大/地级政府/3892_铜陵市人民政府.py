from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3892",
    "page_type": "入口脚本内嵌领导JSON",
    "structure_group": "tongling_channels_tag_children_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML内嵌JSON并脚本跳转",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "embedded_json",
    "collector": "raw_http",
    "parser": "page_inline_tongling_channels_tag_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "script中的channelsTag.children",
    "name_selector": "children[].name",
    "duty_selector": "children[].showName",
    "detail_link_selector": "children[].urls.pc",
    "risk_flag": "入口HTML执行脚本后跳转首位个人页；必须保留原始响应并解析当前栏目children数组",
    "confidence": "high",
    "filter_policy": "strong_json_fields",
}


def clean_text(value: object) -> str:
    """清理HTML标签及排版空白，不改写职务语义。"""
    soup = BeautifulSoup(str(value or ""), "lxml")
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", soup.get_text(" ", strip=True)).strip()


def clean_name(value: object) -> str:
    """仅删除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def decode_assigned_json(html: str, variable_name: str) -> object:
    """从JavaScript变量赋值位置按JSON语法解码首个完整值。"""
    match = re.search(rf"\bvar\s+{re.escape(variable_name)}\s*=\s*", html)
    if match is None:
        raise RuntimeError(f"未找到JavaScript变量：{variable_name}")
    value, _ = json.JSONDecoder().raw_decode(html[match.end() :])
    return value


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按入口栏目children数组原始顺序抽取当前展示领导。"""
    payload = decode_assigned_json(html, "channelsTag")
    if not isinstance(payload, dict) or not isinstance(payload.get("children"), list):
        raise RuntimeError("channelsTag中缺少children数组")

    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()
    for item in payload["children"]:
        if not isinstance(item, dict) or item.get("showOrNot") == 0:
            continue
        name = clean_name(item.get("name"))
        duty = clean_text(item.get("showName"))
        try:
            urls = json.loads(str(item.get("urls") or "{}"))
        except json.JSONDecodeError:
            continue
        href = str(urls.get("pc") or "").strip() if isinstance(urls, dict) else ""
        detail_url = urljoin(base_url, href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            continue
        if not duty or name in seen_names:
            continue
        if urlparse(detail_url).scheme not in {"http", "https"}:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": "入口script中channelsTag.children姓名、展示职务与PC链接",
            }
        )

    if not rows:
        raise RuntimeError("channelsTag.children未提取到有效人物")
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

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
