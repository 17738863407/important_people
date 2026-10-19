from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """压缩网页排版空白，不改变简介原句。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()


def clean_current_evidence(value: str) -> str:
    """删除现任句固定标签、纯句末句号及独立“兼”状态标记。"""
    evidence = re.sub(r"^现任\s*", "", clean_text(value))
    evidence = re.sub(r"(?:（兼）|\(兼\)|<兼>|＜兼＞)", "", evidence)
    return re.sub(r"。$", "", evidence).strip()


def extract_detail(detail_html: str) -> tuple[str, str]:
    """从详情人物区提取姓名及领导简历中的完整现任句。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    region = soup.select_one(".Con_Right")
    region_text = clean_text(region.get_text(" ", strip=True) if region else "")
    name_match = re.search(r"姓\s*名[:：]\s*(?P<name>[\u4e00-\u9fff·]{2,8})", region_text)
    name = name_match.group("name") if name_match else ""

    intro = soup.select_one(".Con_Right .lingdaojl")
    intro_text = clean_text(intro.get_text(" ", strip=True) if intro else "")
    duty_match = re.search(r"现任[^。]*。", intro_text)
    evidence = clean_current_evidence(duty_match.group(0)) if duty_match else ""
    return name, evidence


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导成员目录顺序在线请求详情并提取当前人物证据。"""
    import requests

    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, link in enumerate(soup.select(".zfxxgk_zdgkc a[href][title]"), start=1):
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        response = session.get(detail_url, timeout=30, verify=False)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        name, evidence = extract_detail(response.text)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": response.url,
                "source_order": str(source_order),
                "confidence": "high" if evidence else "medium",
                "parser": "page_inline_guizhou_academy_detail_intro_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "0808",
    "page_type": "人物目录详情页",
    "structure_group": "贵州科学院领导目录转详情简介",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_guizhou_academy_detail_intro_v2",
    "leader_region_selector": ".zfxxgk_zdgkc",
    "name_selector": ".Con_Right姓名字段",
    "duty_selector": ".Con_Right .lingdaojl内完整现任句",
    "detail_link_selector": ".zfxxgk_zdgkc a[href][title]",
    "detail_strategy": {
        "required": True,
        "mode": "custom_online_detail",
        "detail_collector_type": "requests",
    },
    "risk_flag": "详情页含页脚和政策链接，解析范围限定在.Con_Right人物区及.ldjl简历区",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
