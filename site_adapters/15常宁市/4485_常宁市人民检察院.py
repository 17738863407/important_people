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
    return re.sub(r"[\s\u2000-\u200f\u202a-\u202e\u2060\u3000\xa0]+", " ", value or "").strip()


def discover_people(html: str, final_url: str) -> list[tuple[str, str]]:
    """按领导班子页面 DOM 顺序发现唯一人物详情页。"""
    soup = BeautifulSoup(html or "", "html.parser")
    detail_pattern = re.compile(r"/bygk/ldbz/\d{6}/t\d{8}_\d+\.shtml$", re.IGNORECASE)
    people: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    seen_names: set[str] = set()
    for anchor in soup.select("a[href]"):
        detail_url = urljoin(final_url, str(anchor.get("href") or "").strip())
        if detail_url in seen_urls or detail_pattern.search(urlparse(detail_url).path) is None:
            continue
        name = clean_text(str(anchor.get("title") or anchor.get_text(" ", strip=True))).replace(" ", "")
        if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) is None:
            continue
        if name in seen_names:
            raise RuntimeError(f"领导班子页面出现同名不同链接：{name}")
        people.append((name, detail_url))
        seen_urls.add(detail_url)
        seen_names.add(name)
    if not people:
        raise RuntimeError("领导班子页面未发现人物详情链接")
    return people


def extract_current_duty(html: str, name: str) -> str:
    """从当前人物详情正文的“现任”句提取完整职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    roots = soup.select("#fontzoom, .trs_editor_view, .TRS_Editor")
    if not roots:
        roots = [soup]
    candidates: list[str] = []
    for root in roots:
        text = clean_text(root.get_text(" ", strip=True))
        if name not in text:
            continue
        for match in re.finditer(r"现任\s*(?P<duty>[^。；;]+)", text):
            duty = clean_text(match.group("duty")).rstrip("，,；;。 ")
            if duty and len(duty) <= 100:
                candidates.append(duty)
    unique = list(dict.fromkeys(candidates))
    if len(unique) != 1:
        raise RuntimeError(f"人物详情页现职候选数量异常：{name}，{len(unique)}")
    return unique[0]


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    """逐个进入人物详情页提取现职。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    rows: list[dict[str, str]] = []
    for name, detail_url in discover_people(html, final_url):
        detail = fetch_html_with_strategy(
            detail_url, strategy="online", timeout=45, referer=final_url
        )
        duty = extract_current_duty(detail.html, name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail.final_url,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "领导班子人物详情正文中的‘现任’字段",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "4485",
    "page_type": "领导班子列表转人物详情页",
    "structure_group": "changning_procuratorate_leader_detail_v1",
    "reuse_scope": "same_site_same_structure",
    "load_mode": "在线页面；逐个请求人物详情页",
    "extract_mode": "list_to_detail",
    "parser": "page_changning_procuratorate_leader_detail_v1",
    "leader_region_selector": "领导班子栏目人物详情链接",
    "name_selector": "人物详情链接文本",
    "duty_selector": "人物详情正文中的‘现任’字段",
    "detail_link_selector": "/bygk/ldbz/YYYYMM/tYYYYMMDD_数字.shtml",
    "detail_strategy": {"required": True, "mode": "current_person_detail"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "列表存在桌面端与移动端重复链接；按详情 URL 去重，并排除详情页分工文字",
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
