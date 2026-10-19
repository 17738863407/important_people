from __future__ import annotations
import re, sys
from pathlib import Path
def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / 'crawler_core').is_dir(): return parent
    raise RuntimeError('未找到包含 crawler_core 的项目根目录')
PAGE_RULE={'rule_id':'4322','page_type':'article_photo_groups','load_mode':'http','parser':'custom','risk':'正文按主席、副主席、秘书长图片组展示，无个人页。','confidence':'high'}
def parse_page(html: str, final_url: str, page_rule: dict[str,str]) -> list[dict[str,str]]:
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,'html.parser'); root=soup.select_one('.nymain_contant'); first=[]; last=[]; duty=''
    for p in [node for node in root.select('p') if node.find_parent('table') is None] if root else []:
        text=re.sub(r'[\s　]+','',p.get_text(' ',strip=True))
        if text in {'主席','副主席','秘书长'}: duty=text; continue
        if re.fullmatch(r'[\u4e00-\u9fff]{2,4}',text) and duty:
            (first if duty == '主席' else last).append({'name':text,'duty':duty,'detail_url':''})
    rows=[]
    for cell in root.select('table td') if root else []:
        text=re.sub(r'[\s　]+','',cell.get_text(' ',strip=True)); match=re.fullmatch(r'(党组成员)?([\u4e00-\u9fff]{2,4})',text)
        if match: rows.append({'name':match.group(2),'duty':'党组成员' if match.group(1) else '副主席','detail_url':''})
    return first + rows + last
def main() -> None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals()); print(f'输出文件：{output_path}')
if __name__ == '__main__': main()
