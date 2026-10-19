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


def normalize_space(text: str) -> str:
    """清理网页排版空白，不改变职务语义。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    """删除姓名节点中的纯排版空白。"""
    return re.sub(r"\s+", "", normalize_space(text))


def is_name(text: str) -> bool:
    """仅接受现任领导段落首个人物链接中的常见中文姓名形式。"""
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", text))


def build_page_rule(rule_id: str) -> dict:
    """构造当前百科页面经过在线浏览器核验的技术规则。"""
    return {
        "rule_id": rule_id,
        "domain": "baike.baidu.com",
        "page_type": "百科现任领导段落",
        "structure_group": "baidu_baike_named_heading_paragraph_2026",
        "reuse_scope": "single_page",
        "load_mode": "浏览器渲染DOM",
        "fetch_mode": "online",
        "force_browser": True,
        "extract_mode": "named_heading_current_leader_sentence",
        "collector": "browser_dom",
        "parser": "page_baidu_baike_current_leader_v1",
        "leader_region_selector": "[data-tag='header'][data-name='现任领导']",
        "name_selector": "[data-tag='paragraph'] a[href]",
        "duty_selector": "[data-tag='paragraph']",
        "detail_link_selector": "[data-tag='paragraph'] a[href]",
        "content_scope": {
            "start_heading": "现任领导",
            "include_selectors": ["[data-tag='header'][data-name='现任领导']", "[data-tag='paragraph']"],
            "exclude_selectors": ["sup[data-tag='ref']", "script", "style"],
        },
        "detail_strategy": {
            "required": False,
            "mode": "first_person_link_after_heading",
            "detail_link_selector": "a[href]",
            "candidate_links": [],
        },
        "risk_flag": "source_is_baidu_baike_current_leader_paragraph",
        "confidence": "medium",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "heading_selector": "[data-tag='header'][data-name='现任领导']",
                "paragraph_selector": "[data-tag='paragraph']",
                "detail_link_selector": "a[href]",
            },
            "api": {"enabled": False, "reason": "普通HTTP返回安全验证页，浏览器渲染DOM包含目标现任领导段落"},
        },
    }


def find_leader_paragraphs(header: Tag) -> list[Tag]:
    """取得“现任领导”标题后的全部正文段落，不越过下一个标题。"""
    paragraphs: list[Tag] = []
    sibling = header.find_next_sibling()
    while sibling is not None:
        if isinstance(sibling, Tag):
            if sibling.get("data-tag") == "header":
                break
            if sibling.get("data-tag") == "paragraph":
                paragraphs.append(sibling)
        sibling = sibling.find_next_sibling()
    return paragraphs


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从“现任领导”标题后的限定段落提取网页明示的当前人物。"""
    soup = BeautifulSoup(html, "html.parser")
    header = soup.select_one("[data-tag='header'][data-name='现任领导']")
    if not isinstance(header, Tag):
        return []
    paragraphs = find_leader_paragraphs(header)
    if not paragraphs:
        return []

    rows: list[dict[str, str]] = []
    for paragraph in paragraphs:
        for reference in paragraph.select("sup[data-tag='ref']"):
            reference.decompose()
        paragraph_text = normalize_space(paragraph.get_text(" ", strip=True))
        duty_match = re.match(r"^(?P<duty>[^：:]+)[：:]", paragraph_text)
        if duty_match is None:
            continue
        duty = normalize_space(duty_match.group("duty")).strip("，,。.；; ")
        if not duty:
            continue

        for person_link in paragraph.select("a[href]"):
            name = clean_name(person_link.get_text(" ", strip=True))
            if not is_name(name):
                continue
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": urljoin(final_url, str(person_link.get("href", ""))),
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": "strategy=custom_parse_page；heading=现任领导；scope=all[data-tag=paragraph]；fields=逐段冒号前职务+首个人物链接",
                }
            )
            break
    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    page_rule = build_page_rule(rule_id)
    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(
        page_rule,
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=False,
    )
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "3554"
    main(rule_id_value)
