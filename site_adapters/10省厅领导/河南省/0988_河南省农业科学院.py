from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0988",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".article-content",
    "row_selector": ".article-content > p",
    "name_selector": ".article-content > p > strong",
    "duty_selector": "同段姓名后、主持/负责/分管/协助/联系前的文本",
    "detail_link_selector": "",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "每个人物段落同时包含职务、主持/负责事项及联系单位，须以职责动词边界截断。",
}


def normalize_text(text: str) -> str:
    """压缩正文中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def normalize_name(text: str) -> str:
    """去除姓名中的排版空格。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(text or "")).strip()


def clean_status_markers(text: str) -> str:
    """仅删除无期限独立状态标记，保留职级及带期限挂职信息。"""
    marker = r"(?:（(?:兼|挂职|主持日常工作|主持工作)）|\((?:兼|挂职|主持日常工作|主持工作)\)|[<＜](?:兼|挂职)[>＞])"
    return re.sub(marker, "", normalize_text(text)).strip()


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按院领导介绍正文段落顺序提取姓名和原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for paragraph in soup.select(".article-content > p"):
        name_node = paragraph.find("strong")
        if name_node is None:
            continue
        raw_name = normalize_text(name_node.get_text(" ", strip=True))
        name = normalize_name(raw_name)
        paragraph_text = normalize_text(paragraph.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not paragraph_text.startswith(raw_name):
            continue

        after_name = paragraph_text[len(raw_name) :].strip()
        duty = re.split(
            r"\s+(?=主持|负责|分管|协助|联系)", after_name, maxsplit=1
        )[0].strip("，,。；;、 ")
        duty = clean_status_markers(duty)
        if not duty:
            continue

        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
            }
        )

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

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
