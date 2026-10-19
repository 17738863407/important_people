from __future__ import annotations
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def extract_detail_duty(detail_html: str, expected_name: str) -> str:
    """从人物详情页顶部姓名、职务区域取得当前人物的具体职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(detail_html, "html.parser")
    fields = soup.select(".wz > a")
    if len(fields) < 2:
        return ""
    detail_name = clean_text(fields[0].get_text(" ", strip=True)).replace(" ", "")
    if detail_name != expected_name:
        return ""
    return clean_text(fields[1].get_text(" ", strip=True)).strip("：:")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按页面右侧市政府领导区域的顺序进入详情页提取具体职务。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".jc_szfld")
    if region is None:
        return []
    source = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    links = region.select(".jc_swsj a.ld_name[href], .jc_other_ld table a[href]")
    for link in links:
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        href = str(link.get("href") or "").strip()
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not href:
            continue
        seen.add(name)
        detail_url = urljoin(source, href)
        detail = fetch_html_with_strategy(
            detail_url,
            strategy="requests",
            force_browser=False,
            timeout=30,
        )
        duty = extract_detail_duty(detail.html, name)
        if not duty:
            continue
        rows.append({
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": detail.final_url,
            "confidence": "high",
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": "右侧.jc_szfld人物链接及详情页.wz顶部姓名职务字段",
        })
    return rows

PAGE_RULE={"rule_id":"3840","page_type":"市委领导页右侧市政府领导列表转详情页","load_mode":"静态HTML直出并逐详情请求","fetch_mode":"online","extract_mode":"list_to_detail","parser":"page_jinchang_government_detail_v2","leader_region_selector":".jc_szfld","name_selector":".jc_swsj a.ld_name[href], .jc_other_ld table a[href]","duty_selector":".wz > a:nth-of-type(2)","detail_link_selector":".jc_swsj a.ld_name[href], .jc_other_ld table a[href]","detail_strategy":{"required":True,"mode":"dynamic_list_links","max_detail_links":20},"locator_strategy":"custom_parse_page","risk_flag":"入口页标题为市委领导；仅取页面右侧.jc_szfld市政府领导区域，具体职务必须进入对应人物详情页提取","confidence":"high","filter_policy":"strong_no_wordlist"}

def main() -> None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals(),update_fetch_memory=False)
    print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
