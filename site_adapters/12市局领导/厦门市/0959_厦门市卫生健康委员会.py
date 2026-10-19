from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0959",
    "page_type": "人物列表完整页",
    "structure_group": "xm_health_intro_detail_chain_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_health_intro_detail_chain_v2",
    "leader_region_selector": "dd.trt-col-10",
    "name_selector": "a[href]文本：姓名简介",
    "duty_selector": "详情正文简介字段，止于分工或分管处室字段",
    "detail_link_selector": "dd.trt-col-10 a[href]",
    "detail_strategy": {"required": True, "mode": "custom_detail_chain"},
    "risk_flag": "详情正文的简介与分工连续；依据只取简介字段，保留机构名并仅归一化确定性排版空格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def fetch_detail(session: requests.Session, detail_url: str) -> str:
    """在线获取人物详情页，失败时显式终止当前脚本。"""
    response = session.get(detail_url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def extract_evidence(html: str, expected_name: str) -> str:
    """从详情正文提取简介职务，并清理固定标签、姓名及确定性排版空格。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".TRS_Editor") or soup.select_one(".content")
    if region is None:
        raise RuntimeError(f"详情页缺少正文容器：{expected_name}")
    text = clean_text(region.get_text(" ", strip=True))
    match = re.search(
        rf"简介[：:]\s*{re.escape(expected_name)}[，,].+?(?=\s*(?:分管处室|分工)[：:]|$)",
        text,
    )
    if match is None:
        raise RuntimeError(f"详情正文缺少可回指的简介职务字段：{expected_name}")
    evidence = re.sub(
        rf"^简介[：:]\s*{re.escape(expected_name)}[，,]\s*",
        "",
        match.group(0),
        count=1,
    )
    evidence = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", evidence)
    evidence = re.sub(r"\s*([、，；：。])\s*", r"\1", evidence)
    return evidence.rstrip("。").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按入口目录顺序逐页提取人物简介职务原文。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    records: list[object] = []
    seen: set[str] = set()
    for link in soup.select(page_rule["detail_link_selector"]):
        title = clean_text(link.get_text(" ", strip=True))
        name_match = re.fullmatch(r"(?P<name>[\u3400-\u9fff·]{2,10})简介", title)
        if name_match is None:
            continue
        name = name_match.group("name")
        if name in seen:
            raise RuntimeError(f"目录人物姓名重复：{name}")
        detail_url = urljoin(page_rule["url"], str(link.get("href") or ""))
        evidence = extract_evidence(fetch_detail(session, detail_url), name)
        seen.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("入口目录中未提取到人物详情链接")
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
