from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """压缩网页文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def clean_name(value: str) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", str(value or "").replace("\u3000", " ").replace("\xa0", " "))


def clean_current_duty(value: str) -> str:
    """对已经定位的完整现任句执行确定性标签与句末标点清洗。"""
    duty = clean_text(value)
    duty = re.sub(r"^现任", "", duty)
    return duty.rstrip("。；; ")


def parse_page(
    _html: str,
    final_url: str,
    _page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """从入口路径动态派生同站公开内容接口，并解析正文人物段落。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    if not final_url:
        raise ValueError("在线采集结果缺少最终入口网址")
    parsed_url = urlparse(final_url)
    content_match = re.search(r"/(\d+)\.html$", parsed_url.path)
    if content_match is None:
        raise ValueError("入口路径末尾未找到可派生公开接口的内容ID")
    content_id = content_match.group(1)
    api_url = urljoin(final_url, f"/content/{content_id}")

    try:
        api_result = fetch_html_with_strategy(api_url, strategy="raw_http")
    except Exception as error:
        raise RuntimeError(f"同站公开内容接口采集失败：{error}") from error
    try:
        payload = json.loads(api_result.html)
    except json.JSONDecodeError as error:
        raise ValueError("同站公开内容接口未返回有效JSON") from error
    if payload.get("code") != 200 or not isinstance(payload.get("data"), dict):
        raise ValueError(f"同站公开内容接口返回失败状态：{payload.get('code')}")
    data = payload["data"]
    if str(data.get("id") or "") != content_id:
        raise ValueError("同站公开内容接口返回的内容ID与入口不一致")
    returned_path = urlparse(str(data.get("h5UrlWhole") or "")).path
    if returned_path != parsed_url.path:
        raise ValueError("同站公开内容接口返回的页面路径与入口不一致")
    article_html = str(data.get("txt") or "")
    if not article_html:
        raise ValueError("同站公开内容接口的txt正文为空")

    article = BeautifulSoup(article_html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；api=由入口末尾内容ID动态派生/content/{id}；"
        "leader=data.txt；row=data.txt直接人物p；name=p首个逗号前文本；"
        "duty=p内完整现任句；detail=none"
    )
    for paragraph in article.select("p"):
        paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"^([\u4e00-\u9fff·\s]{2,12})[,，]", paragraph_text)
        current_match = re.search(r"现任[^。]*。", paragraph_text)
        if name_match is None or current_match is None:
            continue
        name = clean_name(name_match.group(1))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        if name in seen_names:
            raise ValueError(f"公开接口正文出现重复姓名：{name}")
        seen_names.add(name)
        evidence = clean_current_duty(current_match.group(0))
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "confidence": "high",
                "parser": "page_inline_taiyuan_content_api_v1",
                "selector_summary": selector_summary,
            }
        )

    if not rows:
        raise ValueError("同站公开内容接口正文未解析出有效姓名与现任句")
    return rows


PAGE_RULE = {
    "rule_id": "2691",
    "page_type": "公开内容接口正文页",
    "structure_group": "taiyuan_jeecms_content_api_article",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "api_article_blocks",
    "collector": "static_http",
    "parser": "page_inline_taiyuan_content_api_v1",
    "leader_region_selector": "同站/content/{入口内容ID}响应 data.txt",
    "name_selector": "data.txt > p[包含现任句]首个逗号前文本",
    "duty_selector": "data.txt > p[文本模式=现任至句号]",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "公开页面HTML当前在导航中途截断；使用同站公开内容接口并校验内容ID、页面路径及txt正文",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "同站/content/{入口内容ID}响应 data.txt",
            "name_selector": "data.txt > p[包含现任句]首个逗号前文本",
            "duty_selector": "data.txt > p[文本模式=现任至句号]",
            "detail_link_selector": "",
        },
        "api": {
            "enabled": True,
            "method": "GET",
            "endpoint_rule": "由入口URL末尾数字内容ID动态派生同源/content/{id}",
            "data_path": "data.txt",
            "identity_checks": ["data.id等于入口内容ID", "data.url等于入口路径"],
        },
        "migration": {
            "source": "failed_script_v3_task7",
            "verified_status": "online_verified_20260808",
            "behavior_changed": True,
        },
    },
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
