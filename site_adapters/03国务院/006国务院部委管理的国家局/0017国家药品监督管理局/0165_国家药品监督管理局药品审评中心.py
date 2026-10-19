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
    "rule_id": "0165",
    "page_type": "人物列表完整页",
    "structure_group": "cde_leader_content_paragraph_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "builtin_parse_page",
    "leader_region_selector": "div#content_9f9c74c73e0f8f56a8bfbc646055026d p.articleContent",
    "name_selector": "span.fontw700",
    "duty_selector": "p.articleContent中姓名标签后的原始文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "普通HTTP可能触发动态防护，需由online浏览器链路取得正文",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从药审中心领导正文的姓名强标签及同段剩余文本提取人物。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in soup.select(page_rule["leader_region_selector"]):
        label = paragraph.select_one(page_rule["name_selector"])
        if label is None:
            continue
        raw_label = _clean_text(label.get_text(" ", strip=True))
        name = re.sub(r"\s+", "", raw_label).rstrip("：:")
        line = _clean_text(paragraph.get_text(" ", strip=True))
        evidence = _clean_text(line.replace(raw_label, "", 1)).lstrip("：: ")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": page_rule["parser"],
                "selector_summary": "p.articleContent；span.fontw700姓名；同段剩余文本职务",
            }
        )
    if not records:
        raise RuntimeError("药审中心领导正文未解析到人物记录")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
