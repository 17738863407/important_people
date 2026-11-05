"""按领导列表原顺序读取独立人物页的首个姓名简介段。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "4692",
    "verification_note": "zfxxgk_list内ldxx人物链接，按列表DOM顺序逐页HTTP读取article.article .body中以当前姓名开头的首段，限定完整现任句，移除现任及句末标点，排除分工与履历其他段落",
}


def visible(node):
    for element in [node, *node.parents]:
        style = re.sub(r"\s+", "", str(element.get("style", ""))).lower()
        if element.has_attr("hidden") or element.get("aria-hidden") == "true" or "display:none" in style:
            return False
    return True


def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, "lxml")
    records = []
    for link in soup.select("ul.zfxxgk_list li > a[href]"):
        if not visible(link):
            continue
        detail_url = urljoin(final_url, link["href"])
        if not re.fullmatch(r"/zhengfuxinxigongkai/ldxx/\d+\.html", urlsplit(detail_url).path):
            continue
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
            raise RuntimeError("列表姓名格式异常")
        response = requests.get(detail_url, timeout=15)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        detail = BeautifulSoup(response.text, "lxml")
        title = detail.select_one("article.article h1")
        if title is None or re.sub(r"\s+", "", title.get_text()) != name:
            raise RuntimeError("人物详情页标题与列表姓名不一致")
        paragraphs = [p.get_text("", strip=True) for p in detail.select("article.article .body p") if visible(p)]
        biography = next((text for text in paragraphs if re.sub(r"\s+", "", text).startswith(name + "，")), "")
        current = re.search(r"现任\s*([^。！？]+)[。！？]?", biography)
        if not current:
            raise RuntimeError("当前人物首段没有可核验完整现任句")
        duty = re.sub(r"\s+", "", current.group(1)).strip()
        records.append({"name":name,"evidence":duty,"detail_url":detail_url,
                        "source_name":name,"source_duty":biography})
    return records


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
