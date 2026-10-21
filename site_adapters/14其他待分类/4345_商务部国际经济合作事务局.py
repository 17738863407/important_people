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
    "rule_id": "4345",
    "page_type": "组织机构页职务姓名段落",
    "structure_group": "aieco_org_leader_paragraphs_v1",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_aieco_org_leaders_v1",
    "leader_region_selector": "#articleBody",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文随后还有内设处室图片；仅解析图片前明确的职务姓名段落。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "article_body_role_name_paragraphs",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按正文中的“职务：姓名”段落顺序提取现任负责人。"""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one("#articleBody")
    if article is None:
        raise RuntimeError("未定位到组织结构正文 #articleBody")

    rows: list[dict] = []
    for paragraph in article.select("p"):
        text = " ".join(paragraph.get_text(" ", strip=True).split())
        if "下设" in text:
            break
        match = re.fullmatch(r"([^：:]{2,30})[：:]\s*([\u3400-\u9fff·]{2,6})", text)
        if not match:
            continue
        duty, name = (part.strip() for part in match.groups())
        rows.append({"name": name, "duty": duty, "detail_url": ""})
    if not rows:
        raise RuntimeError("组织结构正文存在，但未解析到职务姓名段落")
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
