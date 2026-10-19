from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3450",
    "page_type": "多人物详情合并页",
    "structure_group": "xm_resources_colleague_scripts_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_resources_colleague_scripts_v2",
    "leader_region_selector": ".gl_tit2 p.tblue1",
    "name_selector": ".gl_tit2 p.tblue1 script内tempchnld",
    "duty_selector": "各详情页.TRS_Editor内完整现任句",
    "detail_link_selector": ".gl_tit2 p.tblue1 script内document.write链接",
    "detail_strategy": {"required": True, "mode": "custom_detail_chain"},
    "risk_flag": "同事链接由在线HTML中的document.write脚本生成，须动态解析脚本文本并逐页验证",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def clean_evidence(value: str) -> str:
    """清除人物简介现任句的固定标签、句末标点和职责分句。"""
    text = re.sub(r"^(?:现任|职务|现任职务)[：:]?", "", clean_text(value)).rstrip("。")
    return re.sub(r"，(?:分管|主持|负责|协管).*$", "", text)


def canonical_url(value: str) -> str:
    """移除片段并统一目录页尾斜杠，用于识别入口回链。"""
    parts = urlsplit(value)
    path = parts.path if parts.path.endswith("/") else f"{parts.path}/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def fetch_detail(session: requests.Session, detail_url: str) -> str:
    """在线获取领导详情页，失败时显式终止当前脚本。"""
    response = session.get(detail_url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def extract_evidence(html: str, expected_name: str) -> str:
    """从当前人物简介正文提取完整现任句。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".TRS_Editor")
    if region is None:
        raise RuntimeError(f"详情页缺少简介正文 .TRS_Editor：{expected_name}")
    text = clean_text(region.get_text(" ", strip=True))
    if expected_name not in re.sub(r"\s+", "", text):
        raise RuntimeError(f"简介正文缺少同事姓名：{expected_name}")
    match = re.search(r"现任[^。]*。", text)
    if match is None:
        raise RuntimeError(f"简介正文缺少完整现任句：{expected_name}")
    return clean_evidence(match.group(0))


def extract_directory(soup: object, final_url: str) -> list[tuple[str, str]]:
    """从同事区在线脚本文本恢复页面实际生成的姓名与链接顺序。"""
    region = soup.select_one(".gl_tit2 p.tblue1")
    if region is None or "我的同事" not in clean_text(region.get_text(" ", strip=True)):
        raise RuntimeError("未找到我的同事脚本区域")
    directory: list[tuple[str, str]] = []
    for script in region.select("script"):
        code = script.string or script.get_text() or ""
        name_match = re.search(r'var\s+tempchnld\s*=\s*"([^"]+)"', code)
        href_match = re.search(r'<a\s+href="([^"]+)"', code)
        if name_match is None or href_match is None:
            continue
        name = re.sub(r"\s+", "", clean_text(name_match.group(1)))
        detail_url = urljoin(final_url, href_match.group(1))
        if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            directory.append((name, detail_url))
    if not directory:
        raise RuntimeError("同事脚本区域中未解析到人物链接")
    return directory


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按同事脚本顺序逐页在线提取姓名、现任句和独立详情链接。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    records: list[object] = []
    seen_names: set[str] = set()
    seen_urls: set[str] = set()
    for name, fetch_url in extract_directory(soup, final_url):
        if name in seen_names or fetch_url in seen_urls:
            raise RuntimeError(f"同事脚本人物或链接重复：{name}")
        evidence = extract_evidence(fetch_detail(session, fetch_url), name)
        detail_url = "" if canonical_url(fetch_url) == canonical_url(page_rule["url"]) else fetch_url
        seen_names.add(name)
        seen_urls.add(fetch_url)
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
