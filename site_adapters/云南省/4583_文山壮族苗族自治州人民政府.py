from __future__ import annotations

from pathlib import Path
import json
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup

PAGE_RULE = {"rule_id": '4583'}


def parse_page(html, final_url, page_rule):
    """解析当前页面channelData中实际供领导卡片使用的JSON数组。"""
    soup = BeautifulSoup(html, 'html.parser')
    script = next((node.get_text() for node in soup.select('script') if 'var channelData' in node.get_text()), '')
    start = script.find('articleLists:')
    if start < 0:
        raise RuntimeError('领导内嵌数组字段缺失')
    data = script[start:]
    keys = {'zzf-data-zz': 'zz100', 'zzf-data-fzz': 'fzz', 'zzf-data-msz': 'msz'}
    rows = []
    for container in soup.select('.leader ul[id]'):
        if any(node.has_attr('hidden') or node.get('aria-hidden') == 'true' or 'display:none' in re.sub(r'\s+', '', node.get('style', '')).lower() for node in [container, *container.parents]):
            continue
        key = keys.get(container.get('id'))
        if not key:
            continue
        match = re.search(r"'" + re.escape(key) + r"'\s*:\s*", data)
        if match is None:
            raise RuntimeError('对应领导分组JSON数组缺失')
        articles, _ = json.JSONDecoder().raw_decode(data[match.end():])
        for item in articles:
            name = str(item.get('title', '')).strip()
            evidence = str(item.get('metadata', {}).get('LeaderIntro', '')).strip()
            urls = json.loads(item.get('urls', '{}'))
            detail = urls.get('common', '')
            if not re.fullmatch(r'[\u3400-\u9fff·]{2,12}', name) or not evidence or not detail:
                raise RuntimeError('领导JSON姓名、职务或独立详情字段缺失')
            rows.append({'name': name, 'evidence': evidence, 'detail_url': urljoin(final_url, detail)})
    if not rows:
        raise RuntimeError('领导数据为空')
    return rows


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
