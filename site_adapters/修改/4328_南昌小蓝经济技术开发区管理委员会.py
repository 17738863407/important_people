from __future__ import annotations

import re
import sys
from urllib.parse import urljoin
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4328",
    "page_type": "leader_page",
    "load_mode": "http",
    "parser": "custom",
    "risk": "按当前分页脚本完整读取领导卡片，仅采领导职务字段，遇WAF或条数不一致显式失败。",
    "confidence": "high",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按当前分页脚本及页面卡片顺序采集所有领导，不把工作分工当职务。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_by_raw_requests
    if "知道创宇云防御" in html or "客户端特征" in html:
        raise RuntimeError("当前入口返回网站防护内容")
    paging=re.search(r"createPageHTML\('page_div',\s*(\d+),\s*1,\s*'([^']+)',\s*'([^']+)',\s*(\d+)\)",html)
    pages=[(html,final_url)]
    if paging:
        total=int(paging.group(1))
        if not 1<=total<=20:
            raise RuntimeError('当前领导栏目页数异常')
        for index in range(2,total+1):
            url=urljoin(final_url,f"{paging.group(2)}_{index}.{paging.group(3)}")
            result=fetch_by_raw_requests(url,timeout=20)
            pages.append((result.html,result.final_url))
    rows=[]
    seen=set()
    for content,page_url in pages:
        soup=BeautifulSoup(content,'html.parser')
        cards=soup.select('#list dl.leader-item')
        if not cards:
            raise RuntimeError('当前分页未发现领导卡片')
        for card in cards:
            if any(n.has_attr('hidden') or n.get('aria-hidden')=='true' or 'display:none' in str(n.get('style','')).replace(' ','') for n in [card,*card.parents]):
                continue
            link=card.select_one('dt h4 a[href]')
            name=re.sub(r'\s+','',link.get_text()) if link else ''
            duty=''
            for field in card.select('.infos'):
                label=field.select_one('label')
                value=field.select_one('.text')
                if label and label.get_text(strip=True).rstrip('：:')=='领导职务' and value:
                    duty=' '.join(value.get_text(' ',strip=True).split())
            if not re.fullmatch(r'[\u3400-\u9fff·]{2,10}',name) or not duty:
                raise RuntimeError('领导卡片缺少可靠姓名或职务')
            if name in seen:
                continue
            seen.add(name)
            rows.append({'name':name,'duty':duty,'evidence':duty,'detail_url':urljoin(page_url,str(link['href']))})
    if paging and len(rows)!=int(paging.group(4)):
        raise RuntimeError(f'领导分页条数与当前页面声明不一致：{len(rows)}')
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
