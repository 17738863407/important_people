from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4399",
    "page_type": "government_leader_cards_by_title",
    "load_mode": "http",
    "fetch_mode": "raw_http",
    "parser": "custom",
    "risk": "仅提取政府领导卡片，使用每人.mingxian完整职务，不从旧分组标题推断。",
    "confidence": "high",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按当前政府领导卡片DOM顺序提取姓名和完整卡片职务。"""
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,'html.parser')
    region=soup.select_one('.szf-zfld .bd')
    if region is None:
        raise RuntimeError('未找到政府领导卡片区域')
    rows=[]
    seen=set()
    for card in region.select('.ct'):
        if any(n.has_attr('hidden') or n.get('aria-hidden')=='true' or 'display:none' in str(n.get('style','')).replace(' ','') for n in [card,*card.parents]):
            continue
        link=card.select_one('h4 a[href]')
        duty_node=card.select_one('.mingxian')
        name=re.sub(r'\s+','',link.get_text()) if link else ''
        duty=' '.join(duty_node.get_text(' ',strip=True).split()) if duty_node else ''
        if not re.fullmatch(r'[\u3400-\u9fff·]{2,10}',name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({'name':name,'duty':duty,'evidence':duty,'detail_url':urljoin(final_url,str(link['href']))})
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
