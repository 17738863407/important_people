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
    "rule_id": "1485",
    "domain": "lyt.ln.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "leader_directory_detail_biography_next_role_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_leader_directory_detail_biography_next_role_v1",
    "leader_region_selector": ".provincial-leaders-inner",
    "detail_link_selector": "a[istitle='true'][href]",
    "detail_biography_selector": ".TRS_Editor p",
    "detail_strategy": {"required": True, "mode": "list_to_detail_biography_next_role"},
    "risk_flag": "公共HTTP把UTF-8误解为Latin-1；需证据化修复编码；职务为本人简历紧随段，不得读页脚",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩详情段落中的排版空白，不改变职务句语义和标点。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def repair_utf8_mojibake(value: str) -> str:
    """仅在Latin-1回转能显著恢复汉字时修复UTF-8误解码。"""
    text = str(value or "")
    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    original_han = sum("\u3400" <= char <= "\u9fff" for char in text)
    repaired_han = sum("\u3400" <= char <= "\u9fff" for char in repaired)
    return repaired if repaired_han > original_han else text


def fetch_detail_duty(
    detail_url: str,
    expected_name: str,
    page_rule: dict[str, object],
    attempt_offset: int,
) -> str:
    """在线核验详情标题和简历姓名，并读取紧随的职务段。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    result = fetch_by_raw_requests(detail_url, timeout=40, attempt_offset=attempt_offset)
    soup = BeautifulSoup(repair_utf8_mojibake(result.html), "html.parser")
    title = clean_name(soup.title.get_text(" ", strip=True) if soup.title else "")
    if title != expected_name:
        return ""

    for paragraph in soup.select(str(page_rule.get("detail_biography_selector", ""))):
        biography = clean_text(paragraph.get_text(" ", strip=True))
        if not biography.startswith(f"{expected_name}，"):
            continue
        sentences = [clean_text(part) for part in biography.split("。") if clean_text(part)]
        for sentence in sentences[1:]:
            if any(keyword in sentence for keyword in ("党组", "局长", "副局长")):
                return f"{sentence}。"
        duty_node = paragraph.find_next_sibling("p")
        if duty_node is not None:
            return clean_text(duty_node.get_text(" ", strip=True))
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口领导目录顺序抓取详情中的相邻职务段。"""
    soup = BeautifulSoup(repair_utf8_mojibake(html or ""), "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    selector = str(page_rule.get("detail_link_selector", ""))
    for source_order, link in enumerate(region.select(selector), start=1):
        name = clean_name(link.get("title") or link.get_text(" ", strip=True))
        href = str(link.get("href", ""))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not href or name in seen:
            continue
        detail_url = urljoin(final_url or source_url, href)
        try:
            duty = fetch_detail_duty(detail_url, name, page_rule, source_order)
        except Exception:
            continue
        if not duty:
            continue
        duty = duty.removesuffix("。")

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；list=.provincial-leaders-inner title links；"
                    "detail title=name verified；biography=.TRS_Editor p startswith name；"
                    "duty=next sibling p"
                ),
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
