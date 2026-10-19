from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3930",
    "page_type": "富文本分片多人名单",
    "structure_group": "dazhou_cppcc_fragmented_lines_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "page_inline_dazhou_cppcc_fragments_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "#endtext > p.p",
    "name_selector": "冒号后富文本字符串片段",
    "duty_selector": "冒号前主席/副主席/秘书长",
    "detail_link_selector": "none_article_roster",
    "risk_flag": "两字姓名被编辑器拆成相邻单字span；必须按字符串片段顺序两两合并",
    "confidence": "high",
}


def compact_text(value: object) -> str:
    """删除富文本排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def join_name_fragments(fragments: list[str]) -> list[str]:
    """保留完整姓名片段，并将连续单字片段按原顺序两两合并。"""
    names: list[str] = []
    pending = ""
    for fragment in fragments:
        token = compact_text(fragment)
        if not re.fullmatch(r"[\u3400-\u9fff·]+", token):
            continue
        if len(token) == 1:
            pending += token
            if len(pending) == 2:
                names.append(pending)
                pending = ""
            continue
        if pending:
            pending = ""
        if 2 <= len(token) <= 20:
            names.append(token)
    return names


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按正文职务行和富文本字符串片段顺序还原人物名单。"""
    soup = BeautifulSoup(html, "lxml")
    paragraphs = soup.select("#endtext > p.p")
    if not paragraphs:
        raise RuntimeError("未定位到政协领导名单正文段落")

    rows: list[dict] = []
    seen_names: set[str] = set()
    valid_duties = {"主席", "副主席", "秘书长"}
    for paragraph in paragraphs:
        fragments = [compact_text(item) for item in paragraph.stripped_strings]
        colon_index = next((index for index, item in enumerate(fragments) if item in {":", "："}), -1)
        if colon_index <= 0:
            continue
        duty = compact_text("".join(fragments[:colon_index]))
        if duty not in valid_duties:
            continue
        for name in join_name_fragments(fragments[colon_index + 1 :]):
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or name in seen_names:
                continue
            seen_names.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "confidence": "high",
                    "parser": page_rule["parser"],
                    "selector_summary": "#endtext直属职务段落及冒号后字符串片段",
                }
            )

    if not rows:
        raise RuntimeError("政协领导名单正文未提取到有效人物")
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
