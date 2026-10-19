from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1785",
    "page_type": "人物接口数据页",
    "structure_group": "jiangxi_department_article_list_json_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "page_inline_jiangxi_mzt_leader_json_v1",
    "leader_region_selector": "入口页channelsTagSelf中showName=领导信息的子栏目",
    "name_selector": "articleList[].title",
    "duty_selector": "articleList[].metadata.Subtitle",
    "detail_link_selector": "articleList[].urls.pc",
    "detail_strategy": {"required": True, "mode": "dynamic_api_url"},
    "risk_flag": "规则入口是机构概况父栏目，须从当前栏目树动态发现领导信息子栏目",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """确定性清理接口字段中的HTML标签与排版空白。"""
    text = BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True)
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", text).strip()
    return re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)


def find_leader_channel_code(html: str) -> str:
    """从入口页当前栏目树中动态读取“领导信息”子栏目代码。"""
    match = re.search(r'"code":"(col\d+)"[^{}]{0,500}"showName":"领导信息"', html)
    if match is None:
        raise RuntimeError("入口页栏目树中未找到领导信息子栏目")
    return match.group(1)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按公开文章列表JSON顺序读取姓名、原始职务与详情链接。"""
    channel_code = find_leader_channel_code(html)
    api_url = urljoin(final_url, f"/jxsmzt/{channel_code}/{channel_code}-articleList.json")
    response = requests.get(
        api_url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError("领导信息文章列表接口未返回数组")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in payload:
        name = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", clean_text(item.get("title")))
        evidence = clean_text((item.get("metadata") or {}).get("Subtitle"))
        try:
            detail_path = str(json.loads(str(item.get("urls") or "{}"))["pc"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            detail_path = ""
        if (
            not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name)
            or not evidence
            or not detail_path
            or name in seen
        ):
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": urljoin(final_url, detail_path),
                "evidence": evidence,
                "parser": str(page_rule["parser"]),
                "selector_summary": "channelTree=领导信息；api=articleList；name=title；evidence=metadata.Subtitle",
            }
        )

    if not rows:
        raise RuntimeError("领导信息文章列表JSON解析为空")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
