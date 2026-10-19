from __future__ import annotations
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())

def normalize_url(value: str) -> str:
    """规范化网页地址，用于识别同址链接。"""
    parsed = urlsplit(str(value or "").strip())
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))

def parse_profile(html: str, url: str, entry_url: str) -> dict[str, str] | None:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    nodes = soup.select(".leader_top_box .leader_name")
    if len(nodes) < 2: return None
    duty = clean_text(nodes[0].get_text(" ", strip=True))
    name = clean_text(nodes[1].get_text(" ", strip=True)).replace(" ", "")
    if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name): return None
    detail_url = "" if normalize_url(url) == normalize_url(entry_url) else url
    return {"name":name,"duty":"","evidence":duty,"detail_url":detail_url,"confidence":"high","parser":"page_inline_jiaozuo_government_details_v1"}

def fetch_profile(url: str, entry_url: str) -> dict[str, str] | None:
    import requests
    response=requests.get(url,timeout=35,verify=False); response.encoding=response.apparent_encoding
    return parse_profile(response.text,response.url,entry_url)

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按左侧导航顺序并发读取强结构详情页。"""
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,"html.parser"); source=final_url or str(page_rule.get("url",""))
    entry_url=str(page_rule.get("url","")) or source
    links=[urljoin(source,str(a.get("href") or "")) for a in soup.select(".nav_box .nav_list a[href]")]
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures=[None if u.rstrip("/")==source.rstrip("/") else pool.submit(fetch_profile,u,entry_url) for u in links]
        rows=[parse_profile(html,source,entry_url) if f is None else f.result() for f in futures]
    return [row for row in rows if row]

PAGE_RULE={"rule_id":"3838","page_type":"目录转领导详情页","load_mode":"静态HTML直出","fetch_mode":"raw_http","_fetch_mode_override":True,"extract_mode":"list_to_detail","parser":"page_inline_jiaozuo_government_details_v1","leader_region_selector":".nav_box .nav_list","name_selector":".leader_name","duty_selector":".leader_name","detail_link_selector":".nav_list a[href]","locator_strategy":"custom_parse_page","risk_flag":"同站多详情页联机提取","confidence":"high"}

def main() -> None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals(),update_fetch_memory=False)
    print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
