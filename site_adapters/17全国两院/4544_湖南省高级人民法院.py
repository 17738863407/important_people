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
    "rule_id": "4544", "page_type": "法院领导详情链接列表",
    "structure_group": "hunan_high_court_detail_links_v1", "reuse_scope": "single_page",
    "load_mode": "浏览器渲染（站点拒绝普通HTTP客户端）", "force_browser": True,
    "extract_mode": "detail_links", "parser": "page_hunan_high_court_detail_links_v1",
    "leader_region_selector": "#main .list_br ul",
    "name_selector": "#main .list_br ul li a[href]", "duty_selector": "详情页 .text.general 中现任句",
    "detail_link_selector": "#main .list_br ul li a[href]", "detail_strategy": {"required": True, "mode": "browser_detail_pages"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "列表页只给姓名，逐一浏览器读取人物详情的现任句；领导区域中的委员职务全部保留，仅剔除独立法官或监察官等级。",
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_by_playwright

    soup = BeautifulSoup(html or "", "html.parser")
    links = soup.select("#main .list_br ul li a[href]")
    if not links:
        raise RuntimeError("未找到高院领导详情链接列表")
    rows: list[dict[str, str]] = []
    errors: list[str] = []
    for link in links:
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        try:
            detail_result = fetch_by_playwright(detail_url, 30)
            detail_soup = BeautifulSoup(detail_result.html or "", "html.parser")
            content = re.sub(r"\s+", "", detail_soup.select_one(".text.general").get_text(" ", strip=True))
        except Exception as error:
            errors.append(f"{name}:{error}")
            continue
        matches = re.findall(r"现任([^。]+)", content)
        raw_duty = matches[-1] if matches else content
        raw_duty = re.sub(rf"^(?:{re.escape(name)})|(?:{re.escape(name)})$", "", raw_duty).strip("。. ")
        parts = []
        for part in re.split(r"[，,、；;]", raw_duty):
            if not part:
                continue
            if re.search(r"(?:大法官|[一二三四五六七八九十]级高级(?:法官|监察官))$", part):
                continue
            parts.append(part)
        evidence = "、".join(parts)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            continue
        if not any(title in evidence for title in ("院长", "党组", "政治部主任", "纪检监察组组长", "执行局局长", "委员")):
            continue
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": detail_url, "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": "#main列表原序读取人物链接，逐页从.text.general现任句提取；委员职务保留，仅剔除独立法官或监察官等级"})
    if errors:
        raise RuntimeError("部分人物详情页抓取失败：" + "；".join(errors))
    if not rows:
        raise RuntimeError("人物详情页未提取到有效领导职务")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")

if __name__ == "__main__":
    main()
