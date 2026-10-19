from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0998",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".lingdao",
    "row_selector": ".lingdao",
    "name_selector": ".xingming",
    "duty_selector": ".zhiwu",
    "detail_link_selector": ".jieshao a[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "每卡同时含个人简历和工作分工两个同地址链接；职务中的原始中英文标点必须按网页保留。",
}


def normalize_text(text: str) -> str:
    """仅压缩领导卡片中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def clean_status_markers(text: str) -> str:
    """仅删除无期限独立状态标记，保留具体兼任职务和原始标点。"""
    marker = r"(?:（(?:兼|挂职|主持日常工作|主持工作)）|\((?:兼|挂职|主持日常工作|主持工作)\)|[<＜](?:兼|挂职)[>＞])"
    return re.sub(marker, "", normalize_text(text)).strip("，。；;、 ")


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导简介卡片顺序提取强结构字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for card in soup.select(".lingdao"):
        name_node = card.select_one(".xingming")
        duty_node = card.select_one(".zhiwu")
        detail_link = card.select_one(".jieshao a[href]")
        if name_node is None or duty_node is None:
            continue
        name = normalize_text(name_node.get_text(" ", strip=True))
        duty = clean_status_markers(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
            continue

        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": (
                    urljoin(base_url, str(detail_link.get("href") or ""))
                    if detail_link is not None
                    else ""
                ),
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
