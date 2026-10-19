from __future__ import annotations

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
    "rule_id": "3312",
    "domain": "zfwb.cq.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "chongqing_foreign_affairs_list_to_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_chongqing_foreign_affairs_list_to_detail_v1",
    "leader_region_selector": ".jgzn-fzrxx a[href]:has(p.name)",
    "name_selector": "p.name",
    "detail_strategy": {
        "required": True,
        "mode": "online_current_detail",
        "detail_content_selector": ".ld-box .trs_editor_view",
    },
    "risk_flag": "列表页职务为空，必须按列表DOM顺序在线访问详情页并只在个人简历区提取现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def fetch_detail_sentence(session: requests.Session, detail_url: str, selector: str) -> str:
    """在线取得个人简介区中的完整“现任……”句。"""
    response = session.get(detail_url, timeout=30, verify=False)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    content = soup.select_one(selector)
    if content is None:
        return ""
    text = clean_text(content.get_text(" ", strip=True))
    match = re.search(r"现任[^。]*。", text)
    return match.group(0) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按列表顺序在线解析每个人物详情页的现任职务证据。"""
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    detail_selector = str(page_rule["detail_strategy"]["detail_content_selector"])
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for link in soup.select(str(page_rule["leader_region_selector"])):
        name_node = link.select_one(str(page_rule["name_selector"]))
        if name_node is None:
            continue
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not detail_url:
            continue
        key = (name, detail_url)
        if key in seen:
            continue
        try:
            evidence = fetch_detail_sentence(session, detail_url, detail_selector)
        except requests.RequestException:
            continue
        if not evidence:
            continue
        seen.add(key)
        duty = evidence.removeprefix("现任").removesuffix("。")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
            }
        )
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
