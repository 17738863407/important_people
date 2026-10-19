from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """压缩网页文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def clean_name(value: str) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", str(value or "").replace("\u3000", " ").replace("\xa0", " "))


def parse_page(
    html: str,
    final_url: str,
    _page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """抓取页面公开iframe，并仅解析其中的领导信息面板。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    frame = soup.select_one("iframe#dataList[src]")
    if frame is None:
        raise ValueError("入口页未找到领导信息iframe iframe#dataList[src]")
    if not final_url:
        raise ValueError("在线采集结果缺少最终入口网址")
    frame_url = urljoin(final_url, str(frame.get("src") or ""))

    try:
        frame_result = fetch_html_with_strategy(frame_url, strategy="raw_http")
    except Exception as error:
        raise RuntimeError(f"领导信息iframe采集失败：{error}") from error
    frame_soup = BeautifulSoup(frame_result.html, "html.parser")
    region = frame_soup.select_one("#jgcon3 #heightbox3 > .view")
    if region is None:
        raise ValueError("iframe未找到领导信息面板 #jgcon3 #heightbox3 > .view")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；frame=iframe#dataList[src]；"
        "leader=#jgcon3 #heightbox3 > .view；row=直接子p且包含完整现任句；"
        "name=p首个逗号前文本；detail=none"
    )
    for paragraph in region.find_all("p", recursive=False):
        paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"^([\u4e00-\u9fff·\s]{2,12})[,，]", paragraph_text)
        current_match = re.search(r"现任[^。]*。", paragraph_text)
        if name_match is None or current_match is None:
            continue
        name = clean_name(name_match.group(1))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        if name in seen_names:
            raise ValueError(f"领导信息面板出现重复姓名：{name}")
        seen_names.add(name)
        evidence = re.sub(
            r"^现任(?:职务)?\s*[：:]?\s*",
            "",
            current_match.group(0),
        ).strip()
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "confidence": "high",
                "parser": "page_inline_nanjing_foreign_affairs_iframe_v1",
                "selector_summary": selector_summary,
            }
        )

    if not rows:
        raise ValueError("领导信息面板未解析出有效姓名与现任句")
    return rows


PAGE_RULE = {
    "rule_id": "2856",
    "page_type": "iframe多人物合并页",
    "structure_group": "nanjing_foreign_affairs_leader_iframe",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "iframe_article_blocks",
    "collector": "static_http",
    "parser": "page_inline_nanjing_foreign_affairs_iframe_v1",
    "leader_region_selector": "iframe#dataList[src] -> #jgcon3 #heightbox3 > .view",
    "name_selector": "#jgcon3 #heightbox3 > .view > p[包含现任句]首个逗号前文本",
    "duty_selector": "#jgcon3 #heightbox3 > .view > p[文本模式=现任至句号]",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "iframe同时承载机构职能、内设机构和领导信息；仅解析领导专属面板#jgcon3，排除工作分工段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "iframe#dataList[src] -> #jgcon3 #heightbox3 > .view",
            "name_selector": "#jgcon3 #heightbox3 > .view > p[包含现任句]首个逗号前文本",
            "duty_selector": "#jgcon3 #heightbox3 > .view > p[文本模式=现任至句号]",
            "detail_link_selector": "",
        },
        "api": {
            "enabled": False,
            "reason": "入口及iframe静态HTML稳定提供领导专属面板和完整现任句",
        },
        "migration": {
            "source": "failed_script_v3_task7",
            "verified_status": "online_verified_20260808",
            "behavior_changed": True,
        },
    },
}


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
