"""逐个读取政府领导人物页的限定简历区现任句。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "4716",
    "verification_note": "当前leaderImgDl dd独立人物卡片顺序，列表duty为空，逐页读取leaderImgC简历区以当前姓名开头段落的完整现任句，排除分工区域，去掉现任及句末标点，保留全部任职限定",
}


def visible(node):
    for element in [node,*node.parents]:
        style = re.sub(r"\s+","",element.get("style",""))
        if element.has_attr("hidden") or element.get("aria-hidden") == "true" or "display:none" in style:
            return False
    return True


def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html,"lxml")
    records = []
    for card in soup.select(".leaderImg .leaderImgDl dd"):
        if not visible(card):
            continue
        name_node = card.select_one(".text .name")
        link = card.select_one("a.con[href]")
        if name_node is None or link is None:
            raise RuntimeError("当前人物卡片字段缺失")
        name = re.sub(r"\s+","",name_node.get_text())
        detail_url = urljoin(final_url,link["href"])
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}",name) or not re.search(r"/ldyview/\d+/\d+\.html$",urlsplit(detail_url).path):
            raise RuntimeError("姓名或独立人物链接异常")
        response = requests.get(detail_url,timeout=15)
        response.raise_for_status()
        response.encoding = "utf-8"
        detail = BeautifulSoup(response.text,"lxml")
        title = detail.select_one(".leaderImgDuty")
        if title is None or re.sub(r"\s+","",title.get_text()) != name:
            raise RuntimeError("独立人物页与当前姓名不匹配")
        paragraphs = [p.get_text("",strip=True) for p in detail.select(".leaderImgC .leaderImgText p") if visible(p)]
        biography = next((text for text in paragraphs if re.sub(r"\s+","",text).startswith(name + "，")),"")
        current = re.search(r"现任\s*([^。！？]+)[。！？]?",biography)
        if not current:
            raise RuntimeError("当前人物限定简历区没有完整现任句")
        duty = re.sub(r"\s+","",current.group(1)).strip()
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
        sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE,globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
