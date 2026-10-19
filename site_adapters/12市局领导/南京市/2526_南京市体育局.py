from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2526",
    "page_type": "人物列表完整页",
    "structure_group": "iframe_image_followed_by_biography_v1",
    "reuse_scope": "single_page",
    "load_mode": "iframe嵌入",
    "fetch_mode": "chrome",
    "extract_mode": "custom_parse_page",
    "collector": "chrome_cdp",
    "parser": "page_inline_iframe_image_biography_v1",
    "iframe_selector": "iframe[name='dataList'][src]",
    "leader_region_selector": "#znjj #heightbox1 .view",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "外页不含人物文本；只解析dataList iframe中当前可见领导信息标签页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """只清理网页排版空白及标点前空格。"""
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def clean_current_evidence(value: str) -> str:
    """仅删除已定位现职句句首的“现任”固定标签。"""
    return re.sub(r"^现任(?:职务)?\s*[：:]?\s*", "", value, count=1)


def fetch_frame_html(frame_url: str) -> str:
    """在隔离子进程中通过Chrome CDP读取同站iframe，避免嵌套同步事件循环。"""
    from crawler_core.fetcher import fetch_by_chrome_debug_subprocess

    return fetch_by_chrome_debug_subprocess(frame_url, timeout=40).html


def parse_frame(frame_html: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按frame中人物头像顺序读取下一头像前首个含现任句的简介段落。"""
    soup = BeautifulSoup(frame_html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []
    children = [child for child in region.children if isinstance(child, Tag)]
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, node in enumerate(children):
        if node.name != "p" or node.find("img") is None:
            continue
        biography = ""
        for candidate in children[index + 1 :]:
            if candidate.name == "p" and candidate.find("img") is not None:
                break
            text = clean_text(candidate.get_text(" ", strip=True))
            if "现任" in text:
                biography = text
                break
        name_match = re.match(r"^([\u3400-\u9fff·]{2,4})，", biography)
        evidence_match = re.search(r"现任[^。]*。", biography)
        if not name_match or not evidence_match:
            continue
        name = name_match.group(1)
        evidence = clean_current_evidence(evidence_match.group(0))
        if name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization") or ""),
                "url": str(page_rule.get("url") or ""),
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "evidence": evidence,
                "confidence": "high",
                "parser": str(page_rule.get("parser") or ""),
                "selector_summary": (
                    "iframe[name=dataList]；#znjj #heightbox1 .view；"
                    "人物头像p img；下一头像前首个含现任句的简介p"
                ),
            }
        )
    return records


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """动态发现iframe地址并解析其人物正文。"""
    soup = BeautifulSoup(html or "", "html.parser")
    frame = soup.select_one(str(page_rule.get("iframe_selector", "")))
    if frame is None or not frame.get("src"):
        return []
    frame_url = urljoin(final_url or str(page_rule.get("url") or ""), str(frame.get("src")))
    return parse_frame(fetch_frame_html(frame_url), page_rule)


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
