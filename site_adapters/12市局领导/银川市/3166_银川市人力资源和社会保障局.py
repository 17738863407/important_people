from __future__ import annotations

import sys
from pathlib import Path
import re

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {'rule_id': '3166',
 'page_type': '人物列表完整页',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'parser': 'page_parse_page',
 'leader_region_selector': '.view.TRS_UEDITOR.trs_word',
 'name_selector': '冒号前标题末尾2至4位中文姓名',
 'duty_selector': '冒号前标题去除末尾姓名',
 'detail_link_selector': '',
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '',
 'confidence': 'high',
 'filter_policy': 'strong_no_wordlist',
 'risk_note': '冒号后均为主持、负责、分管或协助内容，不进入职务依据；末尾AB岗公告不含职务标题。'}


def _clean_text(text: str) -> str:
    text = (text or "").replace("\xa0", " ").replace("\u3000", " ")
    text = " ".join(text.split())
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def _split_title(title: str) -> tuple[str, str]:
    title = _clean_text(title).strip(" ：:")
    forbidden = set("局副委组党工记长员级、，：:()（）")
    for length in (4, 3, 2):
        if len(title) <= length:
            continue
        candidate = title[-length:]
        if any(char in forbidden for char in candidate):
            continue
        position = _clean_text(title[:-length])
        if position and any(keyword in position for keyword in ["局长", "主任", "委员", "调研员"]):
            return candidate, position
    return "", ""


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析银川市人力资源和社会保障局领导分工标题段。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for paragraph in soup.select(".view.TRS_UEDITOR.trs_word p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if "：" not in text and ":" not in text:
            continue
        title, body = re.split(r"[:：]", text, maxsplit=1)
        if not any(keyword in title for keyword in ["局长", "主任", "委员", "调研员"]):
            continue
        name, position = _split_title(title)
        if not name or not position:
            continue
        records.append(
            {
                "name": name,
                "duty": position,
                "detail_url": "",
                "evidence": position,
                "parser": "page_parse_page",
                "selector_summary": "strategy=page_parse_page；region=.view.TRS_UEDITOR.trs_word；name=冒号前标题末尾姓名；duty=标题前缀；detail=none",
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
