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
    "rule_id": "0243",
    "page_type": "多人物详情合并页",
    "structure_group": "隐藏字段注入的多人物简介正文",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "CietcEmbeddedLeaderBiographyParser_v2",
    "leader_region_selector": "#HiddenField1",
    "name_selector": "strong",
    "duty_selector": "当前人物段落内现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "领导正文HTML编码存于HiddenField1，必须限定当前人物段落提取现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析内嵌领导简介，并在每个人物段落内提取完整现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    rendered_paragraphs = soup.select("div.right p")
    paragraphs = [paragraph for paragraph in rendered_paragraphs if "现任" in paragraph.get_text()]
    selector_summary = "div.right p"
    if not paragraphs:
        embedded = soup.select_one("input#HiddenField1")
        embedded_html = embedded.get("value", "") if embedded else ""
        if not embedded_html:
            raise RuntimeError("未找到渲染正文或内嵌领导正文 #HiddenField1")
        embedded_soup = BeautifulSoup(embedded_html, "html.parser")
        paragraphs = [paragraph for paragraph in embedded_soup.select("p") if "现任" in paragraph.get_text()]
        selector_summary = "input#HiddenField1[value] 内嵌HTML p"

    rows: list[dict] = []
    seen: set[str] = set()
    for paragraph in paragraphs:
        name_node = paragraph.select_one("strong")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True)) if name_node else ""
        text = _clean_text(paragraph.get_text(" ", strip=True))
        evidence_match = re.search(r"现任[^。]*。", text)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or evidence_match is None or name in seen:
            continue
        seen.add(name)
        evidence = re.sub(r"^现任\s*", "", evidence_match.group(0))
        evidence = re.sub(r"[。．]\s*$", "", evidence).strip()
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": selector_summary,
            }
        )

    if not rows:
        raise RuntimeError("领导简介未解析到可回指的姓名与现任句")
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
