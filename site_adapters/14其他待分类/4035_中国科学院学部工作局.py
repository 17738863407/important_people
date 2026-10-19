from __future__ import annotations
import re,sys
from pathlib import Path
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4035","page_type":"领导正文页","structure_group":"casad_spaced_leader_lines","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_casad_spaced_leader_lines_v1","leader_region_selector":".trs_editor_view","name_selector":"局长标签后文本","duty_selector":"段首职务标签","detail_link_selector":"","content_scope":{"start_anchor":"现任领导","end_anchor":"附件","include_selectors":[".trs_editor_view"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"副局长姓名使用全角空格逐字排版，按当前文本的连续单字对合并。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验正文内局长、副局长强标签和相邻名单。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":".trs_editor_view"},"api":{"enabled":False,"reason":"HTML正文完整"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    rows=[]
    for p in BeautifulSoup(html,"html.parser").select(".trs_editor_view p"):
        raw=p.get_text(" ",strip=True);m=re.match(r"^(副?局\s*长)\s*[：:]\s*(.*)$",raw)
        if not m:continue
        duty=re.sub(r"\s+","",m.group(1));tokens=re.findall(r"[\u4e00-\u9fff]+",m.group(2));names=["".join(tokens[i:i+2]) for i in range(0,len(tokens),2)] if tokens and all(len(token)==1 for token in tokens) else tokens
        for name in names:
            if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name):rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule["parser"]),"selector_summary":".trs_editor_view p职务—姓名文本"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
