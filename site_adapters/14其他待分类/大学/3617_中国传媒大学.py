from __future__ import annotations
import re,sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
PAGE_RULE={"rule_id":"3617","domain":"by.cuc.edu.cn","page_type":"现任领导响应式职务分组","structure_group":"cuc_mobile_complete_leader_groups_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"complete_group_cards_merge","collector":"static_http","parser":"page_cuc_current_leaders_v1","leader_region_selector":".leaderBox>.leader:last-child","name_selector":".news_title a","duty_selector":".item_title,.news_f1","detail_link_selector":".news_title a[href]","detail_strategy":{"required":False,"mode":"validated_person_link","candidate_links":[]},"risk_flag":"use_complete_mobile_region_avoid_responsive_duplicates","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}
def resolve_project_dir()->Path:
    """向上查找项目根目录。"""
    for p in Path(__file__).resolve().parents:
        if (p/"crawler_core").is_dir():return p
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
def clean(t:str)->str:
    """清理纯排版空白和零宽字符。"""
    return re.sub(r"\s+","",str(t or "").replace("\u200b","").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """只用信息完整的响应式领导区，按分组顺序合并同人职务。"""
    s=BeautifulSoup(html,"html.parser");leaders=s.select(".leaderBox>.leader");r=leaders[-1] if leaders else None;store={}
    if r is None:return []
    for g in r.select(":scope>.leader-classify"):
        gt=g.select_one(".item_title");group_duty=clean(gt.get_text(" ",strip=True) if gt else "")
        for item in g.select("ul.item-con>li.news"):
            a=item.select_one(".news_title a");card=item.select_one(".news_f1");name=clean(a.get_text(" ",strip=True) if a else "");card_duty=clean(card.get_text(" ",strip=True) if card else "")
            if not group_duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name):continue
            if group_duty in card_duty:
                duties=[card_duty]
            elif card_duty in group_duty:
                duties=[group_duty]
            else:
                duties=[value for value in [group_duty,card_duty] if value]
            href=str(a.get("href", "")) if a else "";detail=urljoin(final_url,href) if href and href!="#" and not href.lower().startswith("javascript:") else ""
            row=store.setdefault(name,{"duties":[],"detail_url":detail})
            for duty in duties:
                if duty not in row["duties"]:row["duties"].append(duty)
            if not row["detail_url"] and detail:row["detail_url"]=detail
    return [{"name":n,"duty":"；".join(d["duties"]),"evidence":"；".join(d["duties"]),"detail_url":str(d["detail_url"]),"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=.leaderBox>.leader:last；group=.leader-classify；fields=.item_title+.news_title+.news_f1；duties=merged"} for n,d in store.items()]
def main()->None:
    """运行当前页面级在线爬虫。"""
    p=resolve_project_dir()
    if str(p) not in sys.path:sys.path.insert(0,str(p))
    from crawler_core.runner import run_page_adapter
    c={};o=run_page_adapter(PAGE_RULE,globals(),runtime_context=c,update_fetch_memory=False);print(f"实际采集器：{c.get('actual_collector','')}");print(f"输出文件：{o}")
if __name__=="__main__":
    main()
