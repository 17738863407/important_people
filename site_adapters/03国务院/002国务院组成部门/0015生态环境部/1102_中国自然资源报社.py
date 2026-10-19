from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1102",
    "page_type": "人物列表完整页",
    "structure_group": "iziran_leader_article_api_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "报社领导子栏目的首篇文章content",
    "name_selector": "content p中破折号前文本",
    "duty_selector": "content p中破折号后文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "入口为父栏目动态应用，人物数据由独立API文章提供",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(text: str) -> str:
    """清理接口文章中的排版空白。"""
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def _fetch_json(url: str, params: dict[str, str]) -> dict:
    """通过公共HTTP采集器读取i自然稳定JSON接口。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    query_url = f"{url}?{urlencode(params)}"
    result = fetch_html_with_strategy(query_url, "requests")
    return json.loads(result.html)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """动态发现报社领导栏目文章，并按文章段落顺序提取。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    entry_id = parse_qs(urlsplit(final_url).query).get("id", [""])[0]
    if not entry_id:
        raise RuntimeError("入口URL缺少栏目id")
    api_base = "https://api.iziran.net/api"
    column = _fetch_json(f"{api_base}/getColumn", {"cid": entry_id})
    parent_id = str(column.get("parentID") or "")
    if not parent_id:
        raise RuntimeError("栏目接口未返回parentID")
    subcolumns = _fetch_json(f"{api_base}/getSubColumns", {"cid": parent_id, "type": "0"})
    target = next(
        (
            item
            for item in subcolumns.get("list", [])
            if item.get("column", {}).get("columnName") == "报社领导" and item.get("list")
        ),
        None,
    )
    if target is None:
        raise RuntimeError("子栏目接口未返回报社领导文章")
    article_id = str(target["list"][0].get("fileID") or "")
    article = _fetch_json(f"{api_base}/getArticle", {"aid": article_id})
    soup = BeautifulSoup(str(article.get("content") or ""), "html.parser")

    records: list[PersonRecord] = []
    for paragraph in soup.select("p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·\s]{2,8})[—-]+(?P<duty>.+)", text)
        if match is None:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = _clean_text(match.group("duty"))
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="报社领导接口文章姓名破折号职务段落",
            )
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
