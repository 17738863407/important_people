from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """合并页面排版空白，不改变正文语义。"""
    text = re.sub(r"[\s\u2000-\u200f\u202a-\u202e\u2060\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"\s*([，,、；;：:。])\s*", r"\1", text)


def discover_detail_urls(html: str, final_url: str) -> list[str]:
    """按领导信息栏目 DOM 顺序发现人物详情文章。"""
    soup = BeautifulSoup(html or "", "html.parser")
    pattern = re.compile(r"/cnshbj/zwgk/jggk/ldxx/\d{8}/i\d+\.html$", re.IGNORECASE)
    urls: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        detail_url = urljoin(final_url, str(anchor.get("href") or "").strip())
        if detail_url in seen or pattern.search(urlparse(detail_url).path) is None:
            continue
        urls.append(detail_url)
        seen.add(detail_url)
    if not urls:
        raise RuntimeError("领导信息栏目未发现人物详情文章")
    return urls


def extract_person(html: str) -> tuple[str, str]:
    """从详情正文识别姓名，并从个人简介的“现任”句提取完整职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    text = clean_text(soup.get_text(" ", strip=True))
    name_matches = list(
        re.finditer(
            r"(?P<label>[\u3400-\u9fff、]{2,40})[：:]"
            r"(?P<name>[\u3400-\u9fff·]{2,10})\s*工作分工[：:]",
            text,
        )
    )
    names = list(dict.fromkeys(match.group("name") for match in name_matches))
    if len(names) != 1:
        raise RuntimeError(f"人物详情页姓名候选数量异常：{len(names)}")
    name = names[0]
    current_matches = re.findall(r"现任(?P<duty>[^。；;]+)", text)
    duties = list(dict.fromkeys(clean_text(item).rstrip("，,；;。 ") for item in current_matches if item))
    if len(duties) != 1:
        raise RuntimeError(f"人物详情页现职候选数量异常：{name}，{len(duties)}")
    return name, duties[0]


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    """按栏目顺序逐个进入人物详情页提取完整现职。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for detail_url in discover_detail_urls(html, final_url):
        detail = fetch_html_with_strategy(
            detail_url, strategy="online", timeout=45, referer=final_url
        )
        name, duty = extract_person(detail.html)
        if name in seen_names:
            raise RuntimeError(f"领导信息栏目出现重复姓名：{name}")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail.final_url,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "领导信息栏目人物详情页中个人简介的‘现任’字段",
            }
        )
        seen_names.add(name)
    return rows


PAGE_RULE = {
    "rule_id": "4487",
    "page_type": "领导信息文章列表转人物详情页",
    "structure_group": "changning_ecology_leader_detail_v1",
    "reuse_scope": "same_site_same_structure",
    "load_mode": "WAF 后浏览器渲染；逐个请求人物详情页",
    "extract_mode": "list_to_detail",
    "parser": "page_changning_ecology_leader_detail_v1",
    "leader_region_selector": "领导信息栏目内日期人物文章链接",
    "name_selector": "人物详情正文中工作分工字段前的姓名",
    "duty_selector": "人物详情正文个人简介中的‘现任’字段",
    "detail_link_selector": "/cnshbj/zwgk/jggk/ldxx/YYYYMMDD/i数字.html",
    "detail_strategy": {"required": True, "mode": "current_person_detail"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "列表标题仅含职务不含姓名；必须进入同条个人详情，从简介现任句取完整职务并排除工作分工",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
