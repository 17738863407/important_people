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


PAGE_RULE = {
    "rule_id": "2783",
    "page_type": "人物目录详情页",
    "structure_group": "nmg_sports_leader_columns_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "requests",
    "parser": "inline_parse_page",
    "leader_region_selector": ".leader_box",
    "name_selector": ".leader_info h3 span, .l_leader_list a",
    "duty_selector": ".leaderbox .leaderCon",
    "detail_link_selector": ".leader_info h3 a[href], .l_leader_list a[href]",
    "content_scope": {
        "include_selectors": [".leader_box", ".leaderbox"],
        "exclude_selectors": [".mail_btn"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_raw_http_detail",
        "detail_content_selector": ".leaderbox",
    },
    "risk_flag": "入口主卡和附属领导列表共同构成当前人物顺序，逐详情提取完整现任句并排除分管工作与简历其他内容",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def normalize_text(value: str) -> str:
    """只压缩页面排版空白。"""
    return " ".join((value or "").replace("\u3000", " ").split())


def normalize_name(value: str) -> str:
    """删除姓名节点中的纯排版空白。"""
    return re.sub(r"\s+", "", normalize_text(value))


def discover_people(html: str, final_url: str) -> list[tuple[str, str]]:
    """按两列领导区DOM顺序发现主卡和附属列表人物。"""
    soup = BeautifulSoup(html, "html.parser")
    columns = soup.select(".leader_box .l_leader")
    if not columns:
        raise ValueError("领导简介区域未发现人物列")

    candidates: list[tuple[str, str]] = []
    for column in columns:
        main_link = column.select_one(".leader_info h3 a[href]")
        if main_link is not None:
            name_node = main_link.select_one("span")
            candidates.append(
                (
                    normalize_name(name_node.get_text(" ", strip=True) if name_node else ""),
                    urljoin(final_url, str(main_link.get("href") or "").strip()),
                )
            )
        for extra_link in column.select(".l_leader_list a[href]"):
            candidates.append(
                (
                    normalize_name(extra_link.get_text(" ", strip=True)),
                    urljoin(final_url, str(extra_link.get("href") or "").strip()),
                )
            )

    people: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    seen_urls: set[str] = set()
    for name, detail_url in candidates:
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            raise ValueError(f"入口领导姓名格式异常：{name!r}")
        if name in seen_names or detail_url in seen_urls:
            continue
        seen_names.add(name)
        seen_urls.add(detail_url)
        people.append((name, detail_url))
    return people


def parse_detail(html: str, expected_name: str, detail_url: str) -> dict[str, str]:
    """从当前人物详情最小容器中提取完整现任职务原句。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".leaderbox")
    if region is None:
        raise ValueError(f"人物详情页缺少领导正文：{detail_url}")
    region_text = normalize_text(region.get_text(" ", strip=True))
    if expected_name not in normalize_name(region_text):
        raise ValueError(f"人物详情正文无法回指入口姓名：{expected_name}，页面={detail_url}")
    evidence_match = re.search(r"现任[^。]*。", region_text)
    if evidence_match is None:
        raise ValueError(f"人物详情正文缺少现任职务原句：{detail_url}")
    evidence = re.sub(r"^现任\s*", "", normalize_text(evidence_match.group(0))).rstrip("。")
    return {
        "name": expected_name,
        "duty": evidence,
        "evidence": evidence,
        "detail_url": detail_url,
    }


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口人物顺序逐详情解析当前领导。"""
    del page_rule
    from crawler_core.fetcher import fetch_by_raw_requests

    rows: list[dict[str, str]] = []
    for name, detail_url in discover_people(html, final_url):
        result = fetch_by_raw_requests(detail_url)
        rows.append(parse_detail(result.html, name, detail_url))
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
