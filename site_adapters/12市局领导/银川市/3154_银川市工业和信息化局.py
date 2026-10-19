from __future__ import annotations

import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3154',
 'page_type': '人物列表完整页',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'parser': 'page_parse_page',
 'leader_region_selector': '.view.TRS_UEDITOR.trs_word',
 'name_selector': 'p strong:first-child',
 'duty_selector': '姓名后第一个句号前的原始职务句',
 'detail_link_selector': '',
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '',
 'confidence': 'high',
 'filter_policy': 'strong_no_wordlist',
 'risk_note': '同段在职务句后继续发布职责，后续段发布分管事项，只保留姓名后的首个职务句。'}


def _clean_text(text: str) -> str:
    text = (text or "").replace("\xa0", " ").replace("\u3000", " ").replace("\u2002", " ")
    return " ".join(text.split())


def _clean_name(text: str) -> str:
    return "".join(_clean_text(text).split())


def _strip_leading_name(text: str, name: str) -> str:
    matched = ""
    cut_index = 0
    for index, char in enumerate(text):
        if char.isspace():
            continue
        matched += char
        cut_index = index + 1
        if matched == name:
            return _clean_text(text[cut_index:].lstrip(" ，,、:："))
        if not name.startswith(matched):
            break
    return _clean_text(text.lstrip(" ，,、:："))


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析银川市工业和信息化局领导分工正文。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for paragraph in soup.select(".view.TRS_UEDITOR.trs_word p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        strong = paragraph.find("strong")
        candidate = _clean_name(strong.get_text(" ", strip=True)) if strong else ""
        if not 2 <= len(candidate) <= 6 or candidate.startswith(("分管", "附件")):
            continue
        remainder = _strip_leading_name(text, candidate)
        duty = remainder.partition("。")[0].strip()
        if not duty:
            continue
        evidence = f"{duty}。" if "。" in remainder else duty
        records.append(
            {
                "name": candidate,
                "duty": evidence,
                "detail_url": "",
                "evidence": evidence,
                "parser": "page_parse_page",
                "selector_summary": "strategy=page_parse_page；region=.view.TRS_UEDITOR.trs_word；name=p strong；duty=姓名后首个句号前原文；detail=none",
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
