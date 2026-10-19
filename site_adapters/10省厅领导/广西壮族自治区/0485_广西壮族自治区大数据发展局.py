from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0485",
    "page_type": "人物目录详情页",
    "structure_group": "gx_data_leader_list_detail_current_sentence_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".zfxxgk-right .zfxxgk-more-list",
    "name_selector": ".zfxxgk-more-list a[title][href]",
    "duty_selector": "详情正文人物区域内完整现任句",
    "detail_link_selector": ".zfxxgk-more-list a[title][href]",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "机构页面沿用旧名称，详情正文现任职务使用自治区数据局现名",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ").replace("\u200b", "")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s*([、，,；;：:。])\s*", r"\1", text)


def _clean_evidence(value: str) -> str:
    """删除无期限独立状态标记，保留具体职务。"""
    text = re.sub(r"^现任\s*", "", _clean_text(value))
    text = re.sub(r"[（(]\s*(?:挂职|兼|主持日常工作)\s*[）)]", "", text)
    return text.removesuffix("。").strip("，,、；;。 ")


def _extract_current_sentence(html: str) -> tuple[str, str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    content = (
        soup.select_one("#ldjj-wrap")
        or soup.select_one(".article-con .trs_editor_view")
        or soup.select_one(".view.TRS_UEDITOR")
        or soup.select_one(".article")
    )
    if content is None:
        return "", ""
    text = _clean_text(content.get_text(" ", strip=True))
    match = re.search(r"现任[^。]*。", text)
    if match is None:
        return "", ""
    evidence = _clean_text(match.group(0))
    duty = _clean_evidence(evidence)
    return duty, duty


def _fetch_detail(url: str) -> tuple[str, str]:
    import requests

    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return _extract_current_sentence(response.text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录顺序抓取独立详情页，并从当前人物区域提取完整现任句。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    entry_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".zfxxgk-right .zfxxgk-more-list a[title][href]"):
        name = re.sub(r"\s+", "", _clean_text(link.get("title") or link.get_text("", strip=True)))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or name in seen:
            continue
        detail_url = urljoin(entry_url, str(link.get("href", "")))
        try:
            duty, evidence = _fetch_detail(detail_url)
        except Exception:
            continue
        if not duty or name not in _clean_text(link.get("title") or link.get_text("", strip=True)):
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": evidence,
                "detail_url": detail_url,
            }
        )

    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
