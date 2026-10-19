from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE={"rule_id":"4320","page_type":"leader_cards","load_mode":"http","parser":"custom","risk":"职务由人物详情栏目路径明确区分。","confidence":"high"}

def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,'html.parser'); rows=[]; roles={'zhuxi':'主席','fuzhuxi':'副主席','mishuchang':'秘书长'}
    for link in soup.select('.pic_list a[href]'):
        duty=next((v for k,v in roles.items() if f'/{k}/' in link['href']), '')
        name=link.get_text(' ',strip=True)
        if name and duty: rows.append({'name':name,'duty':duty,'detail_url':urljoin(final_url,link['href'])})
    return rows

def main() -> None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals()); print(f"输出文件：{output_path}")

if __name__ == "__main__":
    main()
