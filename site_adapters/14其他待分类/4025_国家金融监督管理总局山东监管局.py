from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {"rule_id":"4025","page_type":"总局分支SPA文章页","structure_group":"nfra_static_docclob","reuse_scope":"single_page","load_mode":"接口JSON","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_nfra_static_docclob_token_heading_v1","inline_parser_handles_fetch":True,"inline_fetch_collector":"raw_http","leader_region_selector":"接口data.docClob中的现任领导段","name_selector":"段首冒号前末尾姓名词组","duty_selector":"现任句完整现职","detail_link_selector":"","content_scope":{"start_anchor":"局领导","end_anchor":"文档末尾","include_selectors":["data.docClob p"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"姓名存在逐字空格，按段首冒号前的末尾词组动态拼接。","confidence":"high","profile_reusable":True,"profile_judgement":"已核验静态接口实时返回docClob，姓名与职务均在同段。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"api":{"enabled":True,"endpoint":"/cn/static/data/DocInfo/SelectDocEntityByItemId/data_itemId={itemId}.json","params":{"itemId":"入口查询参数"},"data_path":"data.docClob"},"migration":{"verified_status":"verified"}}}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    entry_url = str(page_rule["url"])
    item_id = parse_qs(urlsplit(entry_url).query).get("itemId", [""])[0]
    origin = f"{urlsplit(entry_url).scheme}://{urlsplit(entry_url).netloc}"
    api_url = f"{origin}/cn/static/data/DocInfo/SelectDocEntityByItemId/data_itemId={item_id}.json"
    session = requests.Session()
    session.trust_env = False
    response = session.get(api_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    doc_html = response.json().get("data", {}).get("docClob", "")
    rows: list[dict[str, str]] = []
    for paragraph in BeautifulSoup(doc_html, "html.parser").select("p"):
        raw = paragraph.get_text(" ", strip=True)
        prefix = raw.split("：", 1)[0] if "：" in raw else ""
        tokens = prefix.split()
        if not tokens:
            continue
        name = tokens[-1]
        if len(name) == 1 and len(tokens) >= 2 and len(tokens[-2]) == 1:
            name = tokens[-2] + name
        evidence_match = re.search(r"现任\s*(.+?)[。．]", raw)
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not evidence_match:
            continue
        duty = re.sub(r"\s+", "", evidence_match.group(1))
        rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule["parser"]),"selector_summary":"静态JSON data.docClob现任领导段"})
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
