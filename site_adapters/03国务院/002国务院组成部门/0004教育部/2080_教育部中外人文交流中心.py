from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2080",
    "page_type": "人物列表完整页",
    "structure_group": "中外人文交流中心领导段落",
    "reuse_scope": "ccipe_center_leader_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "CcipeLeaderColonParagraphParser_v2",
    "leader_region_selector": "#vsb_content_1153",
    "name_selector": "p冒号前文本",
    "duty_selector": "p完整原文",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "全页含大量导航与友情链接，必须限定#vsb_content_1153 p；人物采用姓名在前、职务在后的冒号格式，页面无人物独立详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def _extract_records(html: str, rule: dict) -> list[dict]:
    """兼容新旧正文容器，按段落顺序解析冒号前姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for container in soup.select("#vsb_content_1153, #vsb_content_3396_u131, #vsb_content"):
        for paragraph in container.select("p"):
            evidence = _clean_text(paragraph.get_text(" ", strip=True))
            matched = re.fullmatch(r"([\u4e00-\u9fff·]{2,5})[：:]\s*(.+)", evidence)
            if not matched:
                continue
            name = matched.group(1)
            duty = _clean_text(matched.group(2))
            if name in seen_names:
                continue
            seen_names.add(name)
            records.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "parser": rule["parser"],
                    "selector_summary": "新旧版中心领导正文；姓名：职务完整段落",
                }
            )
    return records


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """旧入口跳到新版首页时，动态跟随同站“中心领导”链接。"""
    records = _extract_records(html, rule)
    if records:
        return records

    soup = BeautifulSoup(html, "html.parser")
    base_host = urlsplit(base_url).netloc.lower()
    leader_url = ""
    for link in soup.select("a[href]"):
        if _clean_text(link.get_text(" ", strip=True)) != "中心领导":
            continue
        candidate = urljoin(base_url, str(link.get("href") or ""))
        if urlsplit(candidate).netloc.lower() == base_host:
            leader_url = candidate
            break
    if not leader_url:
        raise RuntimeError("当前页面未找到可验证的同站中心领导链接")

    from crawler_core.fetcher import fetch_html_with_strategy

    result = fetch_html_with_strategy(
        leader_url,
        strategy="raw_http",
        timeout=30,
        referer=base_url,
    )
    records = _extract_records(result.html, rule)
    if not records:
        raise RuntimeError("中心领导正文未解析到人物记录")
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
