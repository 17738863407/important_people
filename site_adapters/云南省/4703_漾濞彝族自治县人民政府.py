"""组合当前页面县长接口及副县长内嵌数组，继承页面分组顺序。"""
from pathlib import Path
import json
import re
import sys
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "4703",
    "verification_note": "县长由当前channelLists.zz.code调用POST queryList，副县长由当前articleLists.fxz按数组顺序展示，title姓名、showTitle职务、urls.pc独立人物页，不使用元数据旧标签或未调用的getFzz分支",
}


def parse_page(html, final_url, page_rule):
    website = re.search(r'\bwebsiteCode\s*=\s*[\'"]([^\'"]+)', html)
    leader_match = re.search(r"'zz'\s*:\s*", html)
    list_match = re.search(r"'fxz'\s*:\s*", html)
    if not website or not leader_match or not list_match:
        raise RuntimeError("当前页面领导栏目结构已变化")
    channel, _ = json.JSONDecoder().raw_decode(html[leader_match.end():])
    deputies, _ = json.JSONDecoder().raw_decode(html[list_match.end():])
    response = requests.post(urljoin(final_url,"/queryList"), data={"current":1,"pageSize":1,"channelCode[]":channel["code"],"webSiteCode[]":website.group(1)},timeout=15)
    response.raise_for_status()
    data = response.json()["data"]
    if int(data["total"]) != 1:
        raise RuntimeError("县长接口人数变化，需重新核验")
    items = [row["source"] for row in data["results"]] + deputies
    records = []
    for item in items:
        name = re.sub(r"\s+", "", item["title"])
        duty = BeautifulSoup(item.get("showTitle",""),"lxml").get_text(" ",strip=True)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}",name) or not duty or duty == name:
            raise RuntimeError("人物姓名或职务字段异常")
        urls = json.loads(item["urls"])
        detail_path = urls["pc"]
        if not re.fullmatch(r"/.+/pc/content/\d+/content_\d+\.html",detail_path):
            raise RuntimeError("人物独立链接格式变化")
        records.append({"name":name,"evidence":duty,"detail_url":urljoin(final_url,detail_path),
                        "source_name":item["title"],"source_duty":item["showTitle"]})
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
