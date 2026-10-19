from __future__ import annotations
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id":"4002", "page_type":"学院领导职务分组页", "structure_group":"aibo_leader_groups", "reuse_scope":"single_page", "load_mode":"静态HTML直出", "fetch_mode":"raw_http", "extract_mode":"custom", "collector":"raw_http", "parser":"custom_aibo_leader_groups_v1", "leader_region_selector":".l", "name_selector":".txt .name a[title]", "duty_selector":".txt .tit", "detail_link_selector":"", "content_scope":{"start_anchor":"学院领导", "end_anchor":"相关链接", "include_selectors":[".l"], "exclude_selectors":[]}, "detail_strategy":{"required":False,"mode":"none"}, "risk_flag":"职务按分组标题继承", "confidence":"high", "profile_reusable":False, "profile_judgement":"已核验标题及紧随名单关系", "filter_policy":"strong_no_wordlist", "locator_strategy":"custom_parse_page", "locator":{"css":{"leader_region_selector":".l","name_selector":".txt .name a[title]","duty_selector":".txt .tit"},"api":{"enabled":False,"reason":"HTML结构完整"},"migration":{"verified_status":"verified"}},
}

def clean_text(value: str) -> str: return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    root=BeautifulSoup(html,"html.parser").select_one(".l")
    if root is None: return []
    rows=[]
    for group in root.select(":scope > .txt"):
        duty=clean_text(group.select_one(".tit").get_text(" ",strip=True)) if group.select_one(".tit") else ""
        for node in group.select(".name a[title]"):
            name=clean_text(node.get("title",node.get_text(" ",strip=True)))
            if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name) and duty: rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule.get("parser","")),"selector_summary":".txt .tit + .name"})
    return rows

def main() -> None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals()); print(f"输出文件：{output_path}")

if __name__ == "__main__":
    main()
