from __future__ import annotations
import re
import sys
from collections import OrderedDict
from pathlib import Path
import requests
from bs4 import BeautifulSoup

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "4496",
    "page_type": "纪委监委领导机构JSON正文",
    "structure_group": "hainan_discipline_supervision_api_article_v1",
    "reuse_scope": "single_page",
    "load_mode": "稳定JSON接口",
    "extract_mode": "grouped_article",
    "parser": "page_hainan_discipline_supervision_api_article_v1",
    "leader_region_selector": "文章接口content正文",
    "name_selector": "目标职务strong后的姓名文本",
    "duty_selector": "正文strong职务标题及机构标题",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "仅保留纪委书记/副书记/常委及监委主任/副主任；排除委员名单；页面无法在线核验时明确失败。",
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    base = "https://www.hncdi.gov.cn"
    headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json;charset=UTF-8"}
    menu = requests.post(base + "/web/menu/getMenu4Show4Bgt.json", json={"orgCode": "000001", "chlCode": "lzw_navs_xxgk_ldjg", "hasImg": False, "skipNo": 0, "pageSize": 100}, headers=headers, timeout=30, verify=False).json()["resultData"][0]
    payload = {"orgCode": "000001", "chlCode": "", "menuId": menu["show_menu_id"], "includeChildMenu": "true", "hasImg": "false", "skip": 0, "pageSize": 10, "titleLength": 150, "summaryLength": 10}
    article = requests.post(base + "/web/article/getArticle4Show4Bgt.json", json=payload, headers=headers, timeout=30, verify=False).json()["resultData"][0]
    detail = requests.post(base + "/web/article/getArticleByArticleId.json", data={"articleId": article["show_article_id"]}, timeout=30, verify=False).json()["resultData"]
    soup = BeautifulSoup(detail["content"], "html.parser")
    people: OrderedDict[str, list[str]] = OrderedDict()
    section = ""
    for paragraph in soup.select("p"):
        full = re.sub(r"\s+", "", paragraph.get_text(" ", strip=True))
        if "纪律检查委员会" in full and "委员名单" not in full:
            section = full
            continue
        if full == "海南省监察委员会":
            section = full
            continue
        strong = paragraph.find("strong")
        role = re.sub(r"\s+", "", strong.get_text(" ", strip=True) if strong else "")
        target = ("纪律检查委员会" in section and role in {"书记", "副书记", "常务委员会委员"}) or (section == "海南省监察委员会" and role in {"主任", "副主任"})
        if not target:
            continue
        remainder = paragraph.get_text(" ", strip=True).replace(strong.get_text(" ", strip=True), "", 1)
        for name in re.findall(r"[\u3400-\u9fff]{2,4}", remainder):
            duties = people.setdefault(name, [])
            duty = section + role
            if duty not in duties:
                duties.append(duty)
    rows = [{"name": name, "duty": "；".join(duties), "evidence": "；".join(duties), "detail_url": "", "parser": str(page_rule["parser"]), "selector_summary": "API文章目标职务分组"} for name, duties in people.items()]
    if not rows:
        raise RuntimeError("JSON领导机构文章未提取到目标人物")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")

if __name__ == "__main__":
    main()
