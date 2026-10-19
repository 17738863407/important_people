from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2895",
    "domain": "wjw.hunan.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "hunan_health_table_to_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_hunan_health_table_to_detail_v2",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "历史标记为iframe，当前页面已改为静态表格直出",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白，并清理中文字段中的布局空格。"""
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()
    text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)
    return re.sub(r"\s*([、，,；;：:（）()])\s*", r"\1", text)


def fetch_detail_html(session: requests.Session, detail_url: str) -> str:
    """在线抓取人物详情页，并对瞬时网络错误进行有限重试。"""
    last_error: requests.RequestException | None = None
    for _ in range(3):
        try:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            return response.text
        except requests.RequestException as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("详情页在线抓取未执行")


def extract_detail_duty(detail_html: str) -> str:
    """从详情页独立职务段落提取原文，不读取职责或简介。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    for paragraph in soup.select("p"):
        label = paragraph.select_one("span.tts")
        if label is None or re.sub(r"\s+", "", label.get_text(" ", strip=True)) != "职务":
            continue
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"职务[：:]\s*(.+)", text)
        if match:
            return clean_text(match.group(1)).strip("，,；;。 ")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """继承入口表格顺序，并在线读取对应详情页职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select('td a[title][href*="/jgld/"]'):
        name = re.sub(r"\s+", "", str(link.get("title", "")) or link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(link.get("href", "")))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or name in seen:
            continue
        try:
            detail_html = fetch_detail_html(session, detail_url)
        except requests.RequestException:
            continue
        detail_text = re.sub(
            r"\s+",
            "",
            BeautifulSoup(detail_html, "html.parser").get_text(" ", strip=True),
        )
        duty = extract_detail_duty(detail_html)
        if name not in detail_text or not duty:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；list=td a[title][href*=jgld]；"
                    "detail=p containing span.tts label=职务"
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
