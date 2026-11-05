from __future__ import annotations

from pathlib import Path
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup

PAGE_RULE = {"rule_id": "4581"}


def visible(node) -> bool:
    for current in [node, *node.parents]:
        style = re.sub(r"\s+", "", current.get("style", "")).lower()
        if current.has_attr("hidden") or current.get("aria-hidden") == "true" or "display:none" in style:
            return False
    return True


def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    head = soup.select_one(".zf-img-name a[href]")
    if head is None or not visible(head):
        raise RuntimeError("未找到可见的首位领导职务姓名字段")
    duty, separator, name = head.get_text("", strip=True).rpartition("：")
    if not separator:
        raise RuntimeError("首位领导字段分隔结构变化")
    rows.append({"name": name, "evidence": duty, "detail_url": urljoin(final_url, head["href"])})
    for group in soup.select(".zf-right-sm"):
        title = group.select_one(".zf-right-sm-tt")
        if title is None or not visible(group):
            continue
        duty = title.get_text("", strip=True)
        for item in group.select("ul.zf-list > li"):
            if not visible(item):
                continue
            links = [link for link in item.select("a[href]") if link.get_text(strip=True)]
            if len(links) != 1:
                raise RuntimeError("人物卡片姓名链接数量异常")
            link = links[0]
            rows.append({"name": re.sub(r"\s+", "", link.get_text()), "evidence": duty, "detail_url": urljoin(final_url, link["href"])})
    if any(not re.fullmatch(r"[\u4e00-\u9fff·]{2,12}", row["name"]) or not row["evidence"] for row in rows):
        raise RuntimeError("姓名或职务字段校验失败")
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
