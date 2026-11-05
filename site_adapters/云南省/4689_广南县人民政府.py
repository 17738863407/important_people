"""解析当前政府领导栏目内嵌数组的姓名和Post职务字段。"""
from pathlib import Path
import json
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup

PAGE_RULE = {
    "rule_id": "4689",
    "verification_note": "当前领导栏目listData.articleList数组，title姓名、metadata.Post原始职务、urls.pc独立人物页，严格保持数组顺序，排除履历LeaderIntro及其他栏目导航",
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
        name = re.sub(r"\s+", "", str(article.get("title", "")))
        duty = str(article.get("metadata", {}).get("Post", "")).strip()
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name) or not duty:
            raise RuntimeError("姓名或metadata.Post职务字段异常")
        urls = article.get("urls", {})
        urls = json.loads(urls) if isinstance(urls, str) else urls
        detail_path = str(urls.get("pc", ""))
        if not re.fullmatch(r"/.+/pc/content/content_\d+\.html", detail_path):
            raise RuntimeError("人物urls.pc结构已变化")
        records.append({"name":name,"evidence":duty,"detail_url":urljoin(final_url,detail_path),
                        "source_name":article["title"],"source_duty":duty})
    return records


def resolve_project_dir() -> Path:
    """从当前脚本向上寻找项目标记，兼容任意脚本层级。"""
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
