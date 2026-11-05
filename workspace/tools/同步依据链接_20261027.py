from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


def root_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / 'crawler_core').is_dir():
            return parent
    raise RuntimeError('未找到项目根目录')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_text(data: bytes) -> str:
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return data.decode('gb18030', errors='replace')


def old_evidence_urls(root: Path) -> dict[str, list[str]]:
    base=root/'workspace'/'reports'/'失败修复_20261026'
    result={}
    for group in (1,2,3):
        payload=json.loads((base/f'恢复验收{group}.json').read_text(encoding='utf-8'))
        for record in payload.get('items',payload.get('records',[])):
            urls=[]
            context=record
            audit_path=record.get('audit') or record.get('auditPath')
            if audit_path:
                context=json.loads(Path(audit_path).read_text(encoding='utf-8'))
            for response in context.get('responses',context.get('network',[])):
                url=str(response.get('url',''))
                if int(response.get('status',0) or 0)==200:
                    urls.append(url)
            final=context.get('runtime',{}).get('final_url') or record.get('final_url')
            if final:
                urls.append(final)
            result[record['id']]=list(dict.fromkeys(urls))
    return result


def probe(url: str, names: list[str]) -> dict:
    data={'requested':url,'status':None,'final_url':'','title':'','name_hits':0,'error':'','blocked':False}
    if not url:
        data['error']='领导链接为空'
        return data
    try:
        response=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=(4,10))
        data.update(status=response.status_code,final_url=response.url,content_type=response.headers.get('Content-Type',''),body_sha256=digest(response.content))
        soup=BeautifulSoup(read_text(response.content),'html.parser')
        data['title']=soup.title.get_text(' ',strip=True) if soup.title else ''
        for node in soup.select('script,style'):
            node.decompose()
        visible=re.sub(r'\s+','',soup.get_text(' ',strip=True))
        data['name_hits']=sum(re.sub(r'\s+','',name) in visible for name in names)
        data['blocked']=bool(re.search(r'百度安全验证|知道创宇云防御|PleaseEnableJavaScriptandCookie|AccessDenied',visible[:3000],re.I))
        data['soft_404']=bool(re.search(r'404|Not\s*Found|页面不存在|您访问的页面不存在',data['title'],re.I))
        data['meta_target']=''
        meta=soup.select_one('meta[http-equiv="refresh"],meta[http-equiv="Refresh"]')
        if meta:
            match=re.search(r'url\s*=\s*([^;]+)',str(meta.get('content','')),re.I)
            if match:
                data['meta_target']=urljoin(response.url,match.group(1).strip().strip(chr(34)).strip(chr(39)))
    except requests.RequestException as error:
        data['error']=str(error)
    return data


def candidate_allowed(url: str) -> bool:
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.hostname in ('localhost','127.0.0.1','::1'):
        return False
    if p.path in ('','/') or re.search(r'\.(?:js|css|jpg|jpeg|png|gif|pdf|bin)$',p.path,re.I) or '/api/' in p.path or 'chat/completions' in p.path:
        return False
    return True


def scan_one(item: dict) -> dict:
    old=probe(item['old_url'],item['names'])
    result={**item,'old_probe':old,'proposals':[],'new_url':'','state':'保持原值'}
    if not item['old_url']:
        result['state']='缺少入口，保留'
        return result
    invalid=old['status'] in (404,410) or old.get('soft_404')
    if not invalid:
        result['state']='现有链接可访问' if old['status']==200 and not old['blocked'] else '访问受限或连接失败，暂不替换'
        return result
    for url in item['candidate_urls']:
        if url==item['old_url'] or not candidate_allowed(url):
            continue
        candidate=probe(url,item['names'])
        result['proposals'].append(candidate)
        if candidate['status']==200 and not candidate['blocked'] and not candidate.get('soft_404'):
            needed=min(2,len(item['names']))
            if needed and candidate['name_hits']>=needed and 'json' not in candidate.get('content_type','').lower():
                result['new_url']=url
                result['state']='候选已在线核实，待人工审阅'
                break
    if not result['new_url']:
        result['state']='旧链接失效，未确认替代入口'
    return result


def transform_lines(raw: bytes, transform) -> bytes:
    """逐行保留原编码标记和换行，只替换指定单元格。"""
    bom=b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    text=raw.decode('utf-8-sig')
    lines=text.splitlines(keepends=True)
    changed=[lines[0]]
    position=0
    for line in lines[1:]:
        if not line.strip():
            changed.append(line)
            continue
        ending='\r\n' if line.endswith('\r\n') else '\n' if line.endswith('\n') else ''
        body=line[:-len(ending)] if ending else line
        values=body.split('\t')
        if len(values)!=12:
            raise ValueError('变更目标不符合十二列')
        position+=1
        transform(values,position)
        changed.append('\t'.join(values)+ending)
    return bom+''.join(changed).encode('utf-8')


def apply_updates(root: Path, base: Path) -> None:
    """只同步已审阅URL，必要时清空与新依据相同的详情链接。"""
    from crawler_core.rule_table import load_rule_table
    plan=json.loads((base/'执行清单.json').read_text(encoding='utf-8'))
    rule_path=root/'workspace'/'source_data'/'规则主表.txt'
    rule_raw=rule_path.read_bytes()
    if digest(rule_raw)!=plan['rule_table_sha256']:
        raise RuntimeError('主表在计划后发生变化，停止避免覆盖')
    old_rules=load_rule_table(rule_path)
    snapshots={}
    for item in plan['scope']:
        path=Path(item['file'])
        raw=path.read_bytes()
        if digest(raw)!=item['before_sha256']:
            raise RuntimeError(f'结果文件在核对后发生变化：{path}')
        snapshots[str(path)]=raw
    updates={r['id']:r for r in plan['updates']}
    if len(updates)!=len(plan['updates']):
        raise RuntimeError('更新序号重复')
    old_py={str(p):digest(p.read_bytes()) for p in (root/'site_adapters').rglob('*.py')}
    backup=base/('备份_'+time.strftime('%Y%m%d_%H%M%S'))
    backup.mkdir(parents=True,exist_ok=False)
    backup_master=backup/'规则主表.txt'
    backup_master.write_bytes(rule_raw)
    if backup_master.read_bytes()!=rule_raw:
        raise RuntimeError('主表备份校验失败')
    manifest=[]
    for item in plan['scope']:
        source=Path(item['file'])
        target=backup/'二次'/source.relative_to(root/'outputs'/'二次')
        target.parent.mkdir(parents=True,exist_ok=True)
        raw=snapshots[str(source)]
        target.write_bytes(raw)
        if target.read_bytes()!=raw:
            raise RuntimeError('TXT备份校验失败')
        manifest.append({'original':str(source),'backup':str(target),'sha256':digest(raw)})
    manifest.insert(0,{'original':str(rule_path),'backup':str(backup_master),'sha256':digest(rule_raw)})
    (backup/'原路径及哈希.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    new_files={}
    self_detail_changes=[]
    master_seen=[]
    def edit_master(values,position):
        sequence=values[10]
        if sequence in updates:
            item=updates[sequence]
            if values[9]!=item['old_url']:
                raise RuntimeError(f'主表原链接不一致：{sequence}')
            values[9]=item['new_url']
            master_seen.append(sequence)
    new_master=transform_lines(rule_raw,edit_master)
    if set(master_seen)!=set(updates):
        raise RuntimeError('主表更新清单未完全覆盖')
    affected_rows=0
    for sequence,item in updates.items():
        expected={r['row']:r['url'] for r in item['clear_self_details']}
        raw=snapshots[str(Path(item['file']))]
        def edit_txt(values,position):
            nonlocal affected_rows
            if values[11]!=sequence or values[6]!=item['old_url']:
                raise RuntimeError(f'TXT原链接或序号不一致：{sequence}')
            values[6]=item['new_url']
            affected_rows+=1
            if position in expected:
                if values[10]!=expected[position]:
                    raise RuntimeError(f'详情链接在计划后改变：{sequence}')
                self_detail_changes.append({'id':sequence,'row':position,'old':values[10],'new':''})
                values[10]=''
        new_files[Path(item['file'])]=transform_lines(raw,edit_txt)
    # 完成所有备份与内存变更验证后才开始原地写回。
    rule_path.write_bytes(new_master)
    for path,raw in new_files.items():
        path.write_bytes(raw)
    new_rules=load_rule_table(rule_path)
    if len(new_rules)!=len(old_rules):
        raise RuntimeError('主表行数变化')
    for old,new in zip(old_rules,new_rules):
        allowed={'领导链接'} if old['脚本序号'] in updates else set()
        if any(old[k]!=new[k] for k in old if k not in allowed):
            raise RuntimeError('主表发生范围外字段变化')
    for pathstr,old_raw in snapshots.items():
        path=Path(pathstr)
        current=path.read_bytes()
        if path not in new_files:
            if current!=old_raw:
                raise RuntimeError(f'未分配TXT发生变化：{path}')
            continue
        if current!=new_files[path]:
            raise RuntimeError('写回内容不一致')
        old_rows=[l.split('\t') for l in old_raw.decode('utf-8-sig').splitlines()]
        new_rows=[l.split('\t') for l in current.decode('utf-8-sig').splitlines()]
        if len(old_rows)!=len(new_rows) or old_rows[0]!=new_rows[0]:
            raise RuntimeError('TXT表头或行数改变')
        item=updates[next(r['id'] for r in plan['scope'] if Path(r['file'])==path)]
        row_position=0
        for old,new in zip(old_rows[1:],new_rows[1:]):
            if len(old)==1 and old==['']:
                if old!=new:
                    raise RuntimeError('空行变化')
                continue
            row_position+=1
            allowed={6,10} if any(r['row']==row_position for r in item['clear_self_details']) else {6}
            if len(new)!=12 or any(old[i]!=new[i] for i in range(12) if i not in allowed):
                raise RuntimeError('非链接字段发生变化')
            if new[6]!=item['new_url']:
                raise RuntimeError('主表和TXT链接未同步')
    if any(digest(Path(p).read_bytes())!=sha for p,sha in old_py.items()):
        raise RuntimeError('页面脚本发生非预期变化')
    result={'scope':len(plan['scope']),'rule_rows_updated':len(updates),'txt_updated':len(new_files),'basis_cells_updated':affected_rows,'self_detail_cells_cleared':self_detail_changes,'backup':str(backup),'person_columns_unchanged':True,'page_scripts_unchanged':True,'collection_runs':0,'updates':plan['updates']}
    (base/'更新验收.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    report=['依据链接同步更新结果（2026-10-27）','','核对outputs/二次内124份TXT，仅更新已确认来源的链接，没有重跑人物采集或识别模型。',f'规则主表更新{len(updates)}条领导链接；同步更新{len(new_files)}份TXT、{affected_rows}个依据链接单元格。',f'按契约清空{len(self_detail_changes)}处与新依据页面相同的详情链接。','姓名、职务、排序、职级、地区、依据说明、机构、维护人和脚本序号逐字段保持不变；页面脚本没有修改。','编码标记、换行、行数和表头均保留；主表已通过项目正式加载校验。',f'可恢复备份：{backup}，其中规则主表及全部124份TXT均已按内容和SHA-256校验。','','未确认有效替代入口、缺少入口或暂时访问受限的项目保留原值；不将HTTP200等同于人物采集验收通过。','本报告为链接维护结果，不改变上一轮人物采集成功/失败/人工复核状态。','','脚本序号\t机构\t旧依据链接\t新依据链接']
    report += ['\t'.join([r['id'],r['organization'],r['old_url'],r['new_url']]) for r in plan['updates']]
    (root/'依据链接更新结果_20261027.txt').write_text('\n'.join(report)+'\n',encoding='utf-8')
    logging.info('更新完成：主表%s条，TXT%s份，依据单元格%s个，清空重复详情%s处',len(updates),len(new_files),affected_rows,len(self_detail_changes))
    print(json.dumps({k:v for k,v in result.items() if k!='updates'},ensure_ascii=False))


def main(action: str) -> None:
    root=root_dir()
    sys.path.insert(0,str(root))
    from crawler_core.paths import resolve_project_path
    from crawler_core.rule_table import load_rule_table
    base=resolve_project_path('workspace/reports/依据链接同步_20261027',anchor=__file__)
    base.mkdir(parents=True,exist_ok=True)
    log=resolve_project_path('workspace/log/依据链接同步_20261027.log',anchor=__file__)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s',handlers=[logging.StreamHandler(sys.stdout),logging.FileHandler(log,encoding='utf-8')])
    rules={r['脚本序号']:r for r in load_rule_table()}
    if action=='apply':
        apply_updates(root,base)
        return
    evidence=old_evidence_urls(root)
    items=[]
    for path in sorted((root/'outputs'/'二次').rglob('*.txt')):
        raw=path.read_bytes()
        lines=read_text(raw).splitlines()
        if not lines or len(lines[0].split('\t'))!=12:
            raise ValueError(f'不是十二列结果：{path}')
        cells=[line.split('\t') for line in lines[1:] if line]
        if any(len(c)!=12 for c in cells):
            raise ValueError(f'列数异常：{path}')
        ids={c[11] for c in cells}
        if len(ids)!=1:
            raise ValueError(f'脚本序号不唯一：{path}')
        sequence=next(iter(ids))
        old=rules[sequence]['领导链接']
        if any(c[6]!=old for c in cells):
            raise ValueError(f'TXT和主表依据链接不一致，先保留现场：{path}')
        urls=evidence.get(sequence,[])
        if old.startswith('http://'):
            urls=['https://'+old[len('http://'):]]+urls
        items.append({'id':sequence,'file':str(path),'organization':rules[sequence]['机构名称'],'old_url':old,'names':[c[0] for c in cells if c[0]],'details':list(dict.fromkeys(c[10] for c in cells if c[10])),'candidate_urls':urls,'before_sha256':digest(raw)})
    if action!='scan':
        raise ValueError('当前工具只执行链接核对，不运行页面脚本或导出人物')
    results=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks={pool.submit(scan_one,item):item for item in items}
        for future in as_completed(tasks):
            result=future.result()
            results.append(result)
            logging.info('%s %s %s',result['id'],result['old_probe']['status'],result['state'])
            (base/'链接核对.json').write_text(json.dumps({'count':len(items),'processed':len(results),'items':sorted(results,key=lambda r:r['id'])},ensure_ascii=False,indent=2),encoding='utf-8')
    logging.info('完成%s项链接核对；人物采集脚本调用次数0',len(results))


if __name__=='__main__':
    action=sys.argv[1] if len(sys.argv)>1 else 'scan'
    main(action)
