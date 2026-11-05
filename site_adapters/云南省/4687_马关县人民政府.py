"""解析当前政府领导栏目内嵌的articleList数组。"""
from pathlib import Path
import json
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "4687",
    "verification_note": "当前政府领导栏目listData.articleList，title以排版空白分隔职务姓名，urls.pc独立content人物页，保持数组原顺序，不使用keywords旧标签或summary分工",
}


def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, "lxml")
    scripts = [node.get_text() for node in soup.select("script") if "var listData" in node.get_text()]
    if len(scripts) != 1:
        raise RuntimeError("未唯一定位当前栏目listData")
    match = re.search(r"\barticleList\s*:\s*", scripts[0])
    if not match:
        raise RuntimeError("当前栏目没有articleList字段")
    articles, _ = json.JSONDecoder().raw_decode(scripts[0][match.end():])
    records = []
    for article in articles:
        title = str(article.get("title", "")).strip()
        fields = re.fullmatch(r"(.+?)\s+([\u3400-\u9fff·]{2,15})", title)
        if not fields:
            raise RuntimeError("领导标题未满足已核验职务姓名分隔格式")
        duty, name = fields.groups()
        urls = article.get("urls", {})
        urls = json.loads(urls) if isinstance(urls, str) else urls
        detail_path = str(urls.get("pc", ""))
        if not re.fullmatch(r"/.+/pc/content/content_\d+\.html", detail_path):
            raise RuntimeError("人物urls.pc结构已变化")
        records.append({"name":name,"evidence":duty,"detail_url":urljoin(final_url,detail_path),
                        "source_name":title,"source_duty":title})
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
