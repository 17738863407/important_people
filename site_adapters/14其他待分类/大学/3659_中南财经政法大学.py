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


PAGE_RULE = {
    "rule_id": "3659",
    "page_type": "领导简介卡片列表",
    "structure_group": "zuel_current_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "zuel_current_leader_cards_v1",
    "leader_region_selector": ".news_list.list2",
    "name_selector": "li.news .news_title a",
    "duty_selector": "li.news .news_title a",
    "detail_link_selector": "li.news .news_title a[href]",
    "content_scope": {"include_selectors": [".news_list.list2"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "list_link_only", "max_detail_links": 30},
    "risk_flag": "标题为职务姓名合并文本，个别姓名前无空格；简历含历史任职，禁止从简介抽取职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_space(value: str) -> str:
    """压缩纯排版空白，保留词语之间必要边界。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def _extract_name(title: str, summary: str) -> str:
    """优先由同卡片简介开头回指姓名，否则读取标题末尾独立姓名。"""
    match = re.match(r"^([\u3400-\u9fff·]{2,4})[，,]", summary)
    if match:
        return match.group(1)
    match = re.search(r"(?:^|\s)([\u3400-\u9fff·]{2,4})$", title)
    return match.group(1) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按卡片DOM顺序提取标题中的当前职务与姓名。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".news_list.list2")
    if region is None:
        return []
    records: list[PersonRecord] = []
    for card in region.select(":scope > li.news"):
        anchor = card.select_one(".news_title a[href]")
        if anchor is None:
            continue
        title = _clean_space(anchor.get_text(" ", strip=True) or anchor.get("title", ""))
        summary_node = card.select_one(".news_text")
        summary = _clean_space(summary_node.get_text(" ", strip=True)) if summary_node is not None else ""
        name = _extract_name(title, summary)
        if not name or not title.endswith(name):
            continue
        duty = title[: -len(name)].strip(" ：:、，,；;")
        duty = re.sub(r"\s*、\s*", "、", duty)
        if not duty:
            continue
        records.append(
            PersonRecord(
                organization=page_rule["organization"], url=page_rule["url"], name=name,
                duty=duty, detail_url=urljoin(final_url, str(anchor.get("href", "")).strip()),
                evidence=duty, confidence="high", parser=page_rule["parser"],
                selector_summary=".news_list.list2 > li.news中的.news_title a",
            )
        )
    return records


def main(update_fetch_memory: bool) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=update_fetch_memory)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    update_fetch_memory = False
    main(update_fetch_memory)
