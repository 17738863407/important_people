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
    "rule_id": "2039", "page_type": "人物表格页", "structure_group": "shenyang_agriculture_detail_or_list_duty_v3",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_agriculture_detail_or_list_duty_v3",
    "leader_region_selector": "唯一人物表格tr", "name_selector": "右单元格strong连续排版空白前",
    "duty_selector": "详情当前人物简介p内完整现任句", "detail_link_selector": "左单元格a[href]",
    "detail_strategy": {"required": True, "mode": "limited_inline_detail", "max_detail_links": 50},
    "risk_flag": "列表职务可能以省略号截断；优先逐详情提取完整现任句，详情无现任句时仅允许回退当前行未截断职务",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def extract_current_sentence(html: str, name: str) -> str:
    """只在当前人物简介段落内提取完整“现任……”原句，无命中时返回空值。"""
    soup = BeautifulSoup(html or "", "html.parser")
    matches: list[str] = []
    for paragraph in soup.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if name not in re.sub(r"\s+", "", text) or "现任" not in text:
            continue
        matches.extend(re.findall(r"现任[^。]*。", text))
    if not matches:
        return ""
    if len(matches) != 1:
        raise RuntimeError(f"详情现任句命中数量异常：{name}={len(matches)}")
    return matches[0]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按表格行顺序抓取详情页当前职务原句。"""
    from crawler_core.fetcher import fetch_online_html_with_fallback
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    tables = soup.select("table")
    if len(tables) != 1:
        raise RuntimeError(f"人物表格命中数量异常：{len(tables)}")
    records: list[object] = []
    seen_names: set[str] = set()
    for row in tables[0].select("tr"):
        heading = row.select_one("td:nth-of-type(2) strong")
        detail_link = row.select_one("td:first-of-type a[href]")
        raw_heading = heading.get_text(" ", strip=True) if heading is not None else ""
        parts = re.split(r"[\s\u2000-\u200b\u3000\xa0]{2,}", raw_heading, maxsplit=1)
        if len(parts) != 2:
            raise RuntimeError("人物表格姓名与列表职务分隔异常")
        name = re.sub(r"\s+", "", clean_text(parts[0]))
        list_duty = clean_text(parts[1])
        href = clean_text(detail_link.get("href", "") if detail_link else "")
        detail_url = urljoin(final_url or page_rule["url"], href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not detail_url:
            raise RuntimeError("人物表格姓名或详情链接异常")
        if name in seen_names:
            raise RuntimeError(f"人物表格姓名重复：{name}")
        detail_html = fetch_online_html_with_fallback(detail_url).html
        current_sentence = extract_current_sentence(detail_html, name)
        if current_sentence:
            evidence = current_sentence.removeprefix("现任").removesuffix("。")
        elif list_duty and "..." not in list_duty and "…" not in list_duty:
            evidence = list_duty
        else:
            raise RuntimeError(f"详情无现任句且列表职务不可回退：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("当前页面未提取到人物表格行")
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
