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
    "rule_id": "4347",
    "page_type": "飞书文档组织机构卡片",
    "structure_group": "feishu_block_map_leader_cards_v1",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_feishu_block_map_leaders_v1",
    "leader_region_selector": "script",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面还含新闻中的会长称谓；仅解析组织机构区间内同一卡片的姓名标题和职务标题。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "feishu_client_vars_block_tree",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """从飞书 SSR 的组织机构结构树中提取领导卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    script_text = next(
        (
            script.string or script.get_text()
            for script in soup.find_all("script")
            if "clientVars: Object(" in (script.string or script.get_text())
            and '"block_map"' in (script.string or script.get_text())
        ),
        "",
    )
    prefix = "clientVars: Object("
    suffix = ") }); window.docx"
    if not script_text or prefix not in script_text or suffix not in script_text:
        raise RuntimeError("未定位到飞书文档结构化 block_map")
    start = script_text.index(prefix) + len(prefix)
    end = script_text.rindex(suffix)
    block_map = json.loads(script_text[start:end])["data"]["block_map"]

    def block_text(block_id: str) -> str:
        data = block_map[block_id].get("data", {})
        return str(
            (((data.get("text") or {}).get("initialAttributedTexts") or {}).get("text") or {}).get("0")
            or ""
        )

    page = next(
        (block for block in block_map.values() if block.get("data", {}).get("type") == "page"),
        None,
    )
    if page is None:
        raise RuntimeError("飞书结构数据中缺少页面根节点")
    top_level = page.get("data", {}).get("children", [])
    section_start = next(
        (
            index
            for index, block_id in enumerate(top_level)
            if re.sub(r"\s+", "", block_text(block_id)) == "组织机构"
        ),
        -1,
    )
    if section_start < 0:
        raise RuntimeError("未定位到飞书文档的组织机构标题")
    section_end = next(
        (
            index
            for index in range(section_start + 1, len(top_level))
            if block_map[top_level[index]].get("data", {}).get("type") == "heading1"
        ),
        len(top_level),
    )

    def descendants(block_id: str) -> list[str]:
        result = [block_id]
        for child_id in block_map[block_id].get("data", {}).get("children", []):
            result.extend(descendants(child_id))
        return result

    rows: list[dict] = []
    role_pattern = re.compile(r"副?会长|法人代表|秘书长")
    for top_id in top_level[section_start + 1 : section_end]:
        for block_id in descendants(top_id):
            data = block_map[block_id].get("data", {})
            if data.get("type") != "grid_column":
                continue
            name = ""
            raw_duty = ""
            for child_id in data.get("children", []):
                child_data = block_map[child_id].get("data", {})
                text = block_text(child_id).strip()
                if child_data.get("type") == "heading3":
                    name = re.sub(r"\s+", "", text)
                elif child_data.get("type") == "heading4":
                    raw_duty = re.sub(r"\s+", "", text)
            duties = list(dict.fromkeys(role_pattern.findall(raw_duty)))
            if re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name) and duties:
                rows.append({"name": name, "duty": "；".join(duties), "detail_url": ""})
    if not rows:
        raise RuntimeError("组织机构区间存在，但未解析到姓名职务卡片")
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
