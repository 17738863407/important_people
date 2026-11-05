from __future__ import annotations
import re,sys
from pathlib import Path
def resolve_project_dir()->Path:
 for p in Path(__file__).resolve().parents:
  if (p/'crawler_core').is_dir():return p
 raise RuntimeError('未找到包含 crawler_core 的项目根目录')
PAGE_RULE={'rule_id':'4188','page_type':'学部常委会公示页','load_mode':'静态HTML直出','extract_mode':'list_direct','parser':'page_inline_cae_committee_v1','leader_region_selector':'#zoom','name_selector':'','duty_selector':'','detail_link_selector':'','detail_strategy':{'required':False,'mode':'none'},'confidence':'high','filter_policy':'strong_no_wordlist'}
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict]:
    """限定目标学部本届常委会，完整保留主任、副主任和委员名单。"""
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,'html.parser')
    region=soup.select_one('#zoom')
    if region is None:
        raise RuntimeError('未找到常委会公示正文')
    target=str(page_rule['organization']).removeprefix('中国工程院')
    heading=next((n for n in region.select('p') if n.get_text(' ',strip=True)==target),None)
    if heading is None:
        raise RuntimeError('未找到目标学部本届常委会标题')
    people={}
    current_duty=""
    for paragraph in heading.find_next_siblings():
        text=re.sub(r'\s+','',paragraph.get_text(' ',strip=True))
        if '学部' in text and '常务委员会' in text:
            break
        match=re.fullmatch(r'(主任|副主任|委员)[：:](.+)',text)
        if match is not None:
            current_duty=match.group(1)
            payload=match.group(2)
        elif current_duty:
            payload=text
        else:
            continue
        duty=current_duty
        for token in re.split(r'[、，,]',payload):
            name=re.sub(r'[（(][^）)]*[）)]','',token)
            if not re.fullmatch(r'[\u3400-\u9fff·]{2,10}',name):
                continue
            record=people.setdefault(name,{'name':name,'duties':[]})
            if duty not in record['duties']:
                record['duties'].append(duty)
    return [{'name':p['name'],'duty':'；'.join(p['duties']),'evidence':'；'.join(p['duties']),'detail_url':''} for p in people.values()]

def main()->None:
 d=resolve_project_dir();sys.path.insert(0,str(d)) if str(d) not in sys.path else None
 from crawler_core.runner import run_page_adapter
 print(f'输出文件：{run_page_adapter(PAGE_RULE,globals())}')
if __name__=='__main__':main()
