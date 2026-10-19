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
    "rule_id": "4346",
    "page_type": "协会领导页文本节点",
    "structure_group": "caefi_leader_text_nodes_v1",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_caefi_leaders_v1",
    "leader_region_selector": ".u-art-con",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物与职务为正文直接文本节点，第一位人物的协会职务位于下一独立文本节点。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "article_text_nodes_role_boundary",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """从协会领导正文的直接文本节点提取人物及其现任职务。"""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one(".u-art-con")
    if article is None:
        raise RuntimeError("未定位到协会领导正文 .u-art-con")
    for node in article.select("script, #show_author"):
        node.decompose()

    duty_starts = ("商务部", "常务副会长", "副会长", "会长")
    rows: list[dict] = []
    for raw_text in article.stripped_strings:
        text = re.sub(r"\s+", "", raw_text)
        if not text:
            continue
        split_at = min((text.find(marker) for marker in duty_starts if text.find(marker) > 0), default=-1)
        if split_at > 0:
            name, duty = text[:split_at], text[split_at:]
            if re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
                rows.append({"name": name, "duty": duty, "detail_url": ""})
                continue
        if rows and "会长" in text:
            rows[-1]["duty"] = f"{rows[-1]['duty']}；{text}"
    if not rows:
        raise RuntimeError("协会领导正文存在，但未解析到姓名职务文本")
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
