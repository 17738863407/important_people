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
    "rule_id": "0684",
    "domain": "gdj.jl.gov.cn",
    "page_type": "人物表格页",
    "structure_group": "jilin_broadcast_table_to_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_jilin_broadcast_table_to_detail_v2",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "详情首句混合职务、姓名、并列现职和职责，必须按姓名及职责动词边界拆分",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


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


def extract_current_duty(name: str, detail_html: str) -> str:
    """从详情首句提取姓名前主职务及姓名后非职责性的并列现职。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    scope = soup.select_one(".TRS_Editor")
    if scope is None:
        return ""
    text = clean_text(scope.get_text(" ", strip=True))
    first_sentence = re.split(r"[。；;]", text, maxsplit=1)[0]
    if name not in first_sentence:
        return ""
    prefix, suffix = first_sentence.split(name, 1)
    primary_duty = clean_text(prefix).strip("，,：:。 ")
    suffix = clean_text(suffix).lstrip("，,：:。 ")
    if suffix and not re.match(r"^(主持|协助|负责|分管|联系|继续|承担)", suffix):
        return f"{primary_duty}，{suffix}"
    return primary_duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """继承领导表格顺序，并在线读取对应详情页现职句。"""
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for name_cell in soup.select("div.submain_r td.ldjjbg"):
        link = name_cell.select_one("a[href]")
        name = re.sub(r"\s+", "", name_cell.get_text(" ", strip=True))
        if link is None or not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href", "")))
        try:
            detail_html = fetch_detail_html(session, detail_url)
        except requests.RequestException:
            continue
        detail_text = re.sub(
            r"\s+",
            "",
            BeautifulSoup(detail_html, "html.parser").get_text(" ", strip=True),
        )
        duty = extract_current_duty(name, detail_html)
        duty = re.sub(r"[（(]\s*兼\s*[）)]", "", duty)
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
                    "strategy=custom_parse_page；list=div.submain_r td.ldjjbg a[href]；"
                    "detail=.TRS_Editor first-sentence name-boundary"
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
