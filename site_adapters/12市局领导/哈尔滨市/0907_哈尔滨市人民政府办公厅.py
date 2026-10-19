from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0907",
    "page_type": "人物列表完整页",
    "structure_group": "harbin_channel_intro_leader_section",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http_with_dynamic_channel_discovery",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#detailContent机关简介文章领导区",
    "name_selector": "领导区姓名职务行段首",
    "duty_selector": "姓名后的当前职务文本及相邻续行",
    "detail_link_selector": "",
    "channel_list_path": "/common/getChannelList",
    "search_path_prefix": "/common/search/",
    "content_scope": {
        "start_anchor": "机关简介文章内领导标题",
        "end_anchor": "办公地址",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "入口为频道框架，动态发现最新机关简介文章并限定文末领导区",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def discover_intro_article(entry_url: str, page_rule: dict) -> str:
    parts = urlsplit(entry_url)
    if not parts.scheme or not parts.netloc:
        raise ValueError("规则主表入口网址缺少有效站点基址")
    path_parts = [part for part in parts.path.split("/") if part]
    channel_match = re.search(r"/(c\d+)/", parts.path)
    if not channel_match or not path_parts:
        raise ValueError("无法从规则主表入口解析频道代码")
    base_url = f"{parts.scheme}://{parts.netloc}"
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": base_url + "/"})
    channel_response = session.get(
        urljoin(base_url, page_rule["channel_list_path"]),
        params={"channelCode": channel_match.group(1), "websiteCodeName": path_parts[0]},
        timeout=30,
    )
    channel_response.raise_for_status()
    children = channel_response.json().get("results", {}).get("children", [])
    intro = next((item for item in children if "机关简介" in str(item.get("channelName", ""))), None)
    if not intro or not intro.get("channelId"):
        raise ValueError("频道接口未发现机关简介子频道")
    search_response = session.get(
        urljoin(base_url, page_rule["search_path_prefix"] + str(intro["channelId"])),
        params={
            "_isAgg": "false",
            "_isJson": "true",
            "_pageSize": "10",
            "_template": "index",
            "_rangeTimeGte": "",
            "_channelName": "",
            "page": "1",
        },
        timeout=30,
    )
    search_response.raise_for_status()
    results = search_response.json().get("data", {}).get("results", [])
    article = next(
        (item for item in results if "职能配置" in str(item.get("title", "")) and item.get("url")),
        next((item for item in results if item.get("url")), None),
    )
    if not article:
        raise ValueError("机关简介子频道未返回可用文章")
    return urljoin(base_url, str(article["url"]))


def parse_leader_section(article_html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(article_html, "html.parser")
    paragraphs = soup.select("#detailContent p")
    in_section = False
    rows: list[dict[str, str]] = []
    name_pattern = re.compile(
        r"^(?P<name>[\u4e00-\u9fff](?:[ \u2000-\u200b]*[\u4e00-\u9fff]){1,3})"
        r"\s+(?P<duty>.+)$"
    )
    for paragraph in paragraphs:
        text = clean_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        if not in_section:
            if re.fullmatch(r"[^。；]{0,20}领导[：:]?", text):
                in_section = True
            continue
        if re.match(r"^(?:办公地址|工作时间|联系电话|通信地址|邮政编码|邮箱)", text):
            break
        match = name_pattern.match(text)
        if match:
            name = clean_text(match.group("name")).replace(" ", "")
            duty = clean_text(match.group("duty"))
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "selector_summary": "动态机关简介文章#detailContent领导区姓名职务行",
                }
            )
        elif rows:
            rows[-1]["duty"] = f"{rows[-1]['duty']} {text}"
            rows[-1]["evidence"] = f"{rows[-1]['evidence']} {text}"
    if not rows:
        raise ValueError("机关简介文章未发现可验证的领导名单")
    return rows


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    entry_url = str(page_rule.get("url") or final_url or "")
    article_url = discover_intro_article(entry_url, page_rule)
    response = requests.get(article_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return parse_leader_section(response.text)


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
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
