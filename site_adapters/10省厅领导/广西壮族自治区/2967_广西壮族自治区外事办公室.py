from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2967",
    "page_type": "人物列表完整页",
    "structure_group": "gx_foreign_affairs_group_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".gov-site-right",
    "name_selector": ".second-gird .txt-list a[title][href]",
    "duty_selector": ".second-gird h2 strong或详情当前人物区域完整现任句",
    "detail_link_selector": ".second-gird .txt-list a[title][href]",
    "detail_strategy": {"required": False, "mode": "list_to_detail"},
    "risk_flag": "人物分组混有工作分工通知；新人物详情可能暂时404，届时以入口分组职务为依据并留空详情",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()


def _extract_current_sentence(html: str, name: str) -> tuple[str, str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one(".trs_editor_view") or soup.select_one(".article-con")
    if content is None:
        return "", ""
    text = _clean_text(content.get_text(" ", strip=True))
    if name not in re.sub(r"\s+", "", text):
        return "", ""
    match = re.search(r"现任[^。]*。", text)
    if match is None:
        return "", ""
    evidence = _clean_text(match.group(0))
    cleaned = evidence.removeprefix("现任").removesuffix("。")
    return cleaned, cleaned


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按入口职务分组顺序解析人物，详情可用时升级为完整现任句。"""
    import requests
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    entry_url = final_url or page_rule["url"]
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for group in soup.select(".gov-site-right .second-gird"):
        duty_node = group.select_one("h2.more-chlid-title strong")
        group_duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not group_duty:
            continue
        for link in group.select(".txt-list a[title][href]"):
            name = re.sub(r"\s+", "", _clean_text(link.get("title") or link.get_text("", strip=True)))
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or name in seen:
                continue
            href = urljoin(entry_url, str(link.get("href", "")))
            duty, evidence, detail_url = group_duty, group_duty, ""
            try:
                response = session.get(href, timeout=25)
                response.raise_for_status()
                response.encoding = response.apparent_encoding or response.encoding
                detail_duty, detail_evidence = _extract_current_sentence(response.text, name)
                if detail_duty:
                    duty, evidence, detail_url = detail_duty, detail_evidence, response.url
            except requests.RequestException:
                pass
            seen.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": evidence,
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
