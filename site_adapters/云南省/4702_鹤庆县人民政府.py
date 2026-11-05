"""依当前页面人物分组顺序调用其公开queryList接口。"""
from pathlib import Path
import json
import re
import sys
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "4702",
    "api_path": "/queryList",
    "verification_note": "当前DOM中data-channel分组顺序，channelLists动态栏目code及name，POST queryList的current/pageSize/channelCode[]/webSiteCode[]，data.results.source.title姓名和showTitle职务，showTitle为姓名时使用当前栏目职务标题，保留数组顺序及urls.pc人物页，排除报告会议",
}


def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, "lxml")
    website = re.search(r'\bwebsiteCode\s*=\s*[\'"]([^\'"]+)', html)
    if not website:
        raise RuntimeError("当前页面未提供websiteCode")
    records = []
    for region in soup.select('[id^="data-channel-"]'):
        key = region["id"].removeprefix("data-channel-")
        match = re.search(r"['\"]" + re.escape(key) + r"['\"]\s*:\s*", html)
        if not match:
            raise RuntimeError("当前领导分组缺少channelLists元数据")
        channel, _ = json.JSONDecoder().raw_decode(html[match.end():])
        page = 1
        received = 0
        while True:
            response = requests.post(urljoin(final_url, page_rule["api_path"]),
                data={"current":page,"pageSize":10,"channelCode[]":channel["code"],"webSiteCode[]":website.group(1)}, timeout=15)
            response.raise_for_status()
            data = response.json()["data"]
            results = data["results"]
            for result in results:
                item = result["source"]
                name = re.sub(r"\s+", "", item["title"])
                field = BeautifulSoup(item.get("showTitle", ""), "lxml").get_text(" ", strip=True)
                duty = channel["name"] if not field or field == name else field
                if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name) or not duty:
                    raise RuntimeError("接口姓名或职务字段异常")
                urls = json.loads(item["urls"])
                detail_path = urls["pc"]
                if not re.fullmatch(r"/.+/pc/content/\d+/content_\d+\.html", detail_path):
                    raise RuntimeError("人物详情urls.pc路径变化")
                records.append({"name":name,"evidence":duty,"detail_url":urljoin(final_url,detail_path),
                                "source_name":item["title"],"source_duty":field if field and field != name else channel["name"]})
            received += len(results)
            if received >= int(data["total"]):
                break
            if not results or page >= 100:
                raise RuntimeError("接口分页未完整返回")
            page += 1
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
