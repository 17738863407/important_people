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

PAGE_RULE = {
    "rule_id": "4550", "page_type": "法院领导详情链接列表",
    "structure_group": "jiangxi_high_court_detail_links_v1", "reuse_scope": "single_page",
    "load_mode": "浏览器渲染", "force_browser": True,
    "extract_mode": "detail_links", "parser": "page_jiangxi_high_court_detail_links_v1",
    "leader_region_selector": "#right #main .list_br ul",
    "name_selector": "#right #main .list_br ul li a[href]", "duty_selector": "详情页 .text.general",
    "detail_link_selector": "#right #main .list_br ul li a[href]", "detail_strategy": {"required": True, "mode": "browser_detail_pages"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "列表页只给姓名，逐一浏览器读取人物详情；领导区委员职务和法官等级等当前职务原文均保留。",
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_by_playwright

    soup = BeautifulSoup(html or "", "html.parser")
    links = soup.select("#right #main .list_br ul li a[href]")
    if not links:
        raise RuntimeError("未找到高院班子详情链接列表")
    rows: list[dict[str, str]] = []
    errors: list[str] = []
    for link in links:
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        try:
            result = fetch_by_playwright(detail_url, 30)
            detail_soup = BeautifulSoup(result.html or "", "html.parser")
            node = detail_soup.select_one(".text.general")
            content = re.sub(r"\s+", "", node.get_text(" ", strip=True) if node else "")
        except Exception as error:
            errors.append(f"{name}:{error}")
            continue
        matches = re.findall(r"现任([^。]+)", content)
        raw_duty = (matches[-1] if matches else content).strip("。. ")
        raw_duty = re.sub(r"^" + re.escape(name), "", raw_duty).strip("。. ")
        raw_duty = re.sub(re.escape(name) + r"$", "", raw_duty).strip("。. ")
        evidence = raw_duty
        if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) and evidence and any(title in evidence for title in ("院长", "党组", "政治部主任", "纪检监察组组长", "执行局局长", "委员会委员", "专职委员")):
            rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": detail_url, "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": "#right #main领导列表原序读取详情链接，逐页从.text.general提取完整现任职务；委员同样保留"})
    if errors:
        raise RuntimeError("部分人物详情页抓取失败：" + "；".join(errors))
    if not rows:
        raise RuntimeError("详情页未提取到领导职务")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")

if __name__ == "__main__":
    main()
