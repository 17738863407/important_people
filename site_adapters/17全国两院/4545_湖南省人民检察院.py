from __future__ import annotations
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(value: object) -> str:
    return re.sub(r"[\\s\\u3000\\xa0]+", "", str(value or ""))

PAGE_RULE = {
    "rule_id": "4545", "page_type": "省级检察院分职务领导列表",
    "structure_group": "hunan_procuratorate_role_categories_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML多栏目", "extract_mode": "list_to_detail", "parser": "page_hunan_procuratorate_role_categories_v1",
    "leader_region_selector": ".list-right及.sub角色栏目",
    "name_selector": ".list-right人物文章链接", "duty_selector": ".sub实时栏目名称",
    "detail_link_selector": ".list-right a[href]", "detail_strategy": {"required": True, "mode": "person_article"},
    "locator_strategy": "custom_parse_page", "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "入口重定向检察长栏目；按页面角色栏目顺序抓取检察长、副检察长、党组成员及专职委员；人物文章链接为详情页。",
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html or "", "html.parser")
    category_links: list[tuple[str, str]] = []
    for link in soup.select(".sub a[href]"):
        role = clean(link.get_text(" ", strip=True))
        if role in {"检察长", "副检察长", "党组成员", "专职委员", "检察委员会专职委员"} and role not in {item[0] for item in category_links}:
            category_links.append((role, urljoin(final_url, str(link.get("href") or ""))))
    if len(category_links) < 3:
        raise RuntimeError("实时页面未发现完整的领导角色栏目")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for role, category_url in category_links:
        result = fetch_html_with_strategy(category_url, strategy="requests", timeout=30, referer=final_url)
        category_soup = BeautifulSoup(result.html, "html.parser")
        for link in category_soup.select(".list-right a[href]"):
            href = str(link.get("href") or "")
            name = clean(link.get_text(" ", strip=True))
            if not re.search(r"/\d{6}/\d+\.html$", href) or not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
                continue
            if name in seen:
                continue
            seen.add(name)
            duty = f"湖南省人民检察院{role}"
            rows.append({
                "name": name, "duty": duty, "evidence": duty,
                "detail_url": urljoin(result.final_url, href), "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "实时角色栏目顺序；.list-right人物文章链接；专职委员栏目纳入",
            })
    if not rows:
        raise RuntimeError("领导角色栏目未提取到人物文章")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")

if __name__ == "__main__":
    main()
