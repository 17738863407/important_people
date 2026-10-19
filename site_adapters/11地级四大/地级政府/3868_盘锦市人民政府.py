from __future__ import annotations
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())

def fetch_title(url: str) -> str:
    import requests
    from bs4 import BeautifulSoup
    session = requests.Session(); session.trust_env = False
    response = session.get(url, timeout=25, verify=False)
    response.raise_for_status(); response.encoding = response.apparent_encoding or "utf-8"
    return clean_text(BeautifulSoup(response.text, "html.parser").title.get_text(" ", strip=True))

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按职务分组取人，并用详情页标题验证页面误配链接。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser"); source = final_url or str(page_rule.get("url", "")); candidates = []
    for group in soup.select(".qi_leadersbox"):
        duty_node = group.select_one(".qi_leadersbox_left")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").replace(" ", "")
        for anchor in group.select(".qiupload_title a[href]"):
            name = clean_text(anchor.get_text(" ", strip=True)).replace(" ", "")
            if duty and re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                candidates.append((name, duty, urljoin(source, str(anchor.get("href") or ""))))
    titles: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch_title, url): url for url in dict.fromkeys(x[2] for x in candidates)}
        for future in as_completed(futures):
            try: titles[futures[future]] = future.result()
            except Exception: titles[futures[future]] = ""
    rows = []
    for name, duty, url in candidates:
        verified_url = url if titles.get(url, "").replace(" ", "").startswith(name) else ""
        rows.append({"name": name, "duty": "", "evidence": duty, "detail_url": verified_url,
                     "confidence": "high", "parser": "page_inline_panjin_groups_verified_links_v1"})
    return rows

PAGE_RULE = {"rule_id": "3868", "page_type": "分组领导卡片", "load_mode": "静态HTML直出",
             "fetch_mode": "raw_http", "_fetch_mode_override": True, "extract_mode": "cards",
             "parser": "page_inline_panjin_groups_verified_links_v1", "leader_region_selector": ".qi_leadersbox",
             "name_selector": ".qiupload_title a", "duty_selector": ".qi_leadersbox_left",
             "detail_link_selector": ".qiupload_title a[href]", "locator_strategy": "custom_parse_page",
             "risk_flag": "列表存在误配详情链接，需按详情标题逐项验证", "confidence": "high"}

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")

if __name__ == "__main__": main()
