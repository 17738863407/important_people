from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE={"rule_id":"4321","page_type":"tabbed_leader_cards","load_mode":"http","parser":"custom","risk":"市政府入口以四个标签并列展示，按当前卡片职务中的市政协文本限定。","confidence":"high"}

def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,'html.parser'); rows=[]
    group=next((x for x in soup.select('.tabItem') if '市政协' in x.get_text(' ',strip=True)),None)
    for link in group.select('.col-lead-item[href]') if group else []:
        name=link.select_one('.name'); duty=link.select_one('.pos')
        if name and duty: rows.append({'name':name.get_text(' ',strip=True),'duty':duty.get_text(' ',strip=True).removeprefix('职位：'),'detail_url':urljoin(final_url,link['href'])})
    return rows

def main() -> None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals()); print(f"输出文件：{output_path}")

if __name__ == "__main__":
    main()
