from __future__ import annotations
import re, sys
from pathlib import Path
def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / 'crawler_core').is_dir(): return parent
    raise RuntimeError('未找到包含 crawler_core 的项目根目录')
PAGE_RULE={'rule_id':'4170','page_type':'领导团队接口','load_mode':'官方JSON接口','extract_mode':'api_direct','parser':'page_inline_cssp_leader_api_v2','leader_region_selector':'api:data[]','name_selector':'name','duty_selector':'position','detail_link_selector':'','detail_strategy':{'required':False,'mode':'none'},'confidence':'high','filter_policy':'strong_no_wordlist','inline_parser_handles_fetch':True,'inline_fetch_collector':'requests','api_endpoint':'https://www.csspw.cn/website/api/aboutus/leasers','risk_flag':'入口由规则主表注入新版关于我们页面；接口来自当前公开前端getLeader，姓名职务按data数组原序，详情仅为弹层故留空'}
def parse_page(html:str, final_url:str, page_rule:dict)->list[dict]:
    """读取新版官网公开领导接口，不扫描首页新闻或将弹层作为独立人物页。"""
    import requests

    response = requests.post(str(page_rule['api_endpoint']), timeout=30)
    response.raise_for_status()
    payload = response.json()
    values = payload.get('data')
    if payload.get('code') != 200 or not isinstance(values, list) or not values:
        raise RuntimeError('新版领导团队接口未返回有效data数组')
    rows = []
    for item in values:
        name = re.sub(r'\s+', '', str(item.get('name') or ''))
        duty = re.sub(r'\s+', ' ', str(item.get('position') or '')).strip()
        if not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name) or not duty:
            raise RuntimeError('领导接口姓名或position字段异常')
        rows.append({'name': name, 'duty': duty, 'evidence': duty, 'detail_url': ''})
    return rows
def main()->None:
 project_dir=resolve_project_dir();sys.path.insert(0,str(project_dir)) if str(project_dir) not in sys.path else None
 from crawler_core.runner import run_page_adapter
 print(f'输出文件：{run_page_adapter(PAGE_RULE,globals())}')
if __name__=='__main__': main()
