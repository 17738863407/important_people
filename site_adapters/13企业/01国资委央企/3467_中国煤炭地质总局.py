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
    "rule_id": "3467",
    "page_type": "人物列表完整页",
    "structure_group": "煤炭地质总局管理团队图片人物块",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "CcgcImageListParser_v2",
    "leader_region_selector": ".news_xq .imgList div:has(img) > p",
    "name_selector": "人物段落首行",
    "duty_selector": "人物段落后续行",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "规则入口现返回首页；从入口DOM动态发现“管理团队”链接后抓取，排除同结构空图片段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def _resolve_team_html(html: str, base_url: str) -> tuple[str, str]:
    """入口失效为首页时，动态跟随当前“管理团队”导航链接。"""
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one(".news_xq .imgList") is not None:
        return html, base_url
    team_link = next(
        (
            node
            for node in soup.select("a[href]")
            if _clean_text(node.get_text(" ", strip=True)) == "管理团队"
        ),
        None,
    )
    if team_link is None:
        raise RuntimeError("规则入口未发现当前管理团队导航链接")
    team_url = urljoin(base_url, str(team_link.get("href", "")))
    response = requests.get(
        team_url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按管理团队人物块顺序解析姓名及全部原始职务行。"""
    team_html, _ = _resolve_team_html(html, base_url)
    soup = BeautifulSoup(team_html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for paragraph in soup.select(".news_xq .imgList div:has(img) > p"):
        parts = [
            text
            for item in paragraph.get_text("\n", strip=True).splitlines()
            if (text := _clean_text(item))
        ]
        if len(parts) < 2:
            continue
        name = re.sub(r"\s+", "", parts[0])
        evidence = "；".join(parts[1:])
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".news_xq .imgList人物图片块；p首行姓名、后续行职务",
            }
        )
    if not records:
        raise RuntimeError("煤炭地质总局管理团队未解析到人物记录")
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
