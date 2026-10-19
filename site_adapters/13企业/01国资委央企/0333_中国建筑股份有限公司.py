from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0333",
    "page_type": "人物目录详情页",
    "structure_group": "中建集团领导成员与中建股份高管团队",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_cscec_group_and_shareholder_executives_v3",
    "leader_region_selector": ".yxj-conBox > .yxj-con",
    "risk_flag": "中建集团领导成员与中建股份高管团队存在重复人物及不同详情链接，需按首次网页顺序合并职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    """确定性清理正文排版空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*([、，。；：])\s*", r"\1", text)
    return re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)


def clean_name(value: str) -> str:
    """去除姓名节点中的展示空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def fetch_detail(url: str, session: requests.Session) -> tuple[str, str]:
    """在线取得同站人物详情页。"""
    response = session.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.text, response.url


def extract_duty_sentences(text: str) -> str:
    """取得详情正文开头所有明确属于公司的完整职务句。"""
    sentences = [clean_text(sentence) for sentence in re.findall(r"[^。]+。", clean_text(text))]
    return "".join(sentence for sentence in sentences if "有限公司" in sentence).removesuffix("。")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析集团领导与股份高管，按首次网页顺序合并同名人物职务。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = final_url or str(page_rule.get("url", ""))
    source_host = urlsplit(source_url).netloc.lower()
    tabs = soup.select("ul.yxj-tab > li")
    groups = soup.select("div.yxj-conBox > div.yxj-con")
    candidates: list[dict[str, object]] = []
    candidate_by_name: dict[str, dict[str, object]] = {}
    for tab, group in zip(tabs, groups):
        group_name = clean_text(tab.get_text(" ", strip=True))
        if group_name not in {"中建集团领导成员", "中建股份高管团队"}:
            continue
        for item in group.select("ul.yxj-gltd > li"):
            name_node = item.select_one("h4")
            link = item.select_one("a[href]")
            name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
            detail_url = urljoin(source_url, str(link.get("href", ""))) if link else ""
            parsed = urlsplit(detail_url)
            if (
                re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name)
                and parsed.netloc.lower() == source_host
                and "/gyzj/gltd_new/" in parsed.path
                and parsed.path.endswith(".html")
            ):
                candidate = candidate_by_name.get(name)
                if candidate is None:
                    candidate = {"name": name, "detail_urls": []}
                    candidate_by_name[name] = candidate
                    candidates.append(candidate)
                detail_urls = candidate["detail_urls"]
                if isinstance(detail_urls, list) and detail_url not in detail_urls:
                    detail_urls.append(detail_url)

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": source_url})
    rows: list[dict[str, str]] = []
    for candidate in candidates:
        name = str(candidate["name"])
        detail_urls = candidate["detail_urls"]
        if not isinstance(detail_urls, list):
            continue
        resolved_url = ""
        evidence_values: list[str] = []
        for detail_url in detail_urls:
            detail_html, current_resolved_url = fetch_detail(str(detail_url), session)
            detail_soup = BeautifulSoup(detail_html, "html.parser")
            detail_name_node = detail_soup.select_one("h2.gsywtpc")
            detail_name = clean_name(detail_name_node.get_text(" ", strip=True) if detail_name_node else "")
            content_node = detail_soup.select_one("#gsxwxq")
            evidence = extract_duty_sentences(content_node.get_text(" ", strip=True) if content_node else "")
            if detail_name != name or not evidence:
                continue
            if not resolved_url:
                resolved_url = current_resolved_url
            if evidence not in evidence_values:
                evidence_values.append(evidence)
        if not evidence_values:
            continue
        merged_evidence = "；".join(evidence_values)
        rows.append(
            {
                "name": name,
                "duty": merged_evidence,
                "detail_url": resolved_url,
                "evidence": merged_evidence,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "group=中建集团领导成员/中建股份高管团队；name=h4；detail_name=h2.gsywtpc；duty=#gsxwxq公司职务句",
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
