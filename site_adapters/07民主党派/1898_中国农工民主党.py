from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


RULE_ID = "1898"


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """合并详情正文中的连续空白字符。"""
    return re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_evidence_duty(value: str) -> str:
    """删除现任句的固定前缀及纯句末句号。"""
    evidence = re.sub(r"^现任\s*", "", clean_text(value))
    return re.sub(r"。$", "", evidence).strip()


def extract_current_duty(detail_html: str) -> str:
    """仅在详情正文中提取第一条以“现任”开头的完整职务句。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    content = soup.select_one(".gp-article")
    if content is None:
        return ""
    text = clean_text(content.get_text(" ", strip=True))
    match = re.search(r"现任[^。；;\n\r]{2,300}(?:[。；;]|$)", text)
    return clean_evidence_duty(match.group(0)) if match else ""


def load_detail_duty(
    session: requests.Session,
    detail_url: str,
    referer: str,
    timeout_seconds: int,
) -> str:
    """请求个人详情页并按“现任”规则提取职务。"""
    response = session.get(
        detail_url,
        timeout=timeout_seconds,
        headers={"Referer": referer},
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return extract_current_duty(response.text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """进入中国农工民主党本届领导详情页，按“现任”句提取职务。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    timeout_seconds = int(page_rule.get("detail_timeout_seconds") or 30)
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        for item in soup.select(".sub_right ul.cp-list19 li"):
            link = item.select_one("a[href]")
            if link is None:
                continue
            name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name) or name in seen:
                continue

            detail_url = urljoin(base_url, link.get("href", ""))
            try:
                duty = load_detail_duty(session, detail_url, base_url, timeout_seconds)
            except Exception as error:
                print(f"跳过详情页请求失败的人物：{name}；{detail_url}；{error}")
                continue
            if not duty:
                print(f"详情正文未匹配到“现任”职务句：{name}；{detail_url}")
                continue

            seen.add(name)
            records.append(
                {
                    "organization": str(page_rule.get("organization", "")),
                    "url": base_url,
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": duty,
                    "confidence": "high",
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": ".cp-list19 姓名链接 + 详情正文 .gp-article 的现任句",
                }
            )
    return records


def main(page_rule: dict) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(page_rule, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    page_rule = {
        "rule_id": RULE_ID,
        "page_type": "人物列表完整页",
        "load_mode": "静态HTML直出",
        "fetch_mode": "raw_http",
        "parser": "page_inline_ngd_detail_current_sentence_v2",
        "detail_timeout_seconds": 30,
    }
    main(page_rule)
