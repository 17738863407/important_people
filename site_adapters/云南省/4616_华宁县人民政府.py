from __future__ import annotations

from pathlib import Path
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup

PAGE_RULE = {"rule_id": '4616'}


def parse_page(html, final_url, page_rule):
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for link in soup.select('.conRight > li > span > a[href]'):
        if not link.get('href') or not link.get_text(strip=True):
            continue
        if any(node.has_attr('hidden') or node.get('aria-hidden') == 'true' or 'display:none' in re.sub(r'\s+', '', node.get('style', '')).lower() for node in [link, *link.parents]):
            continue
        name = re.sub(r'\s+', '', link.get_text())
        if not re.fullmatch(r'[\u3400-\u9fff·]{2,12}', name):
            raise RuntimeError('领导列表姓名结构变化')
        detail_url = urljoin(final_url, link['href'])
        response = fetch_by_raw_requests(detail_url, timeout=8, max_retries=2)
        detail = BeautifulSoup(response.html, 'html.parser')
        heading = detail.select_one('.channel-content-main .article-head')
        if heading is None or re.sub(r'\s+', '', heading.get_text()) != name:
            raise RuntimeError('列表姓名与详情标题不一致')
        content = detail.select_one('.channel-content-main .article-main')
        # 本页明确将隐藏模板内容复制到可见正文，这里复现同一确定性DOM赋值。
        assignment = "$('.article-main').html($('.article-main-text').html())"
        if content is not None and not content.get_text(strip=True) and assignment in response.html:
            content = detail.select_one('.article-main-text')
        if content is None:
            raise RuntimeError('详情正文边界缺失')
        paragraphs = [node.get_text('', strip=True) for node in content.select('p, h1, h2, h3, h4, h5, h6') if node.get_text(strip=True)]
        intro = next((text for text in paragraphs if re.sub(r'\s+', '', text).startswith(name + '，')), '')
        match = re.search(r'现任([^。]+)', intro)
        evidence = re.sub(r'\s+', '', match.group(1)) if match else ''
        if not evidence:
            # 部分当前领导简介以第一句末尾的明确职务标签替代现任句。
            label = re.sub(r'\s+', '', intro.split('。', 1)[0].rsplit('，', 1)[-1])
            if re.fullmatch(r'[一二三四]级调研员', label):
                evidence = label
        if not evidence:
            raise RuntimeError('当前人物简介段落缺少完整现职句')
        rows.append({'name': name, 'evidence': evidence, 'detail_url': detail_url, 'raw_evidence': intro})
    if not rows:
        raise RuntimeError('领导列表为空')
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
