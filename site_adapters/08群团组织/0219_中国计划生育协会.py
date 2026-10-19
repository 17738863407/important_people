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


def clean_text(value: str) -> str:
    """压缩网页排版空白，不改写原始语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从桌面端现任领导列表的逐人链接中提取姓名、职务和详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".leaderBoxR.fr")
    if region is None:
        raise RuntimeError("在线页面缺少.leaderBoxR.fr桌面端现任领导区域")

    entry_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in region.select(".bdNow > a[href]"):
        text = clean_text(link.get_text(" ", strip=True))
        parts = re.split(r"\s+(?=党组|会长|副会长|秘书长|主任|理事)", text, maxsplit=1)
        if len(parts) != 2:
            continue

        name = re.sub(r"\s+", "", parts[0])
        duty = parts[1].strip()
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name):
            continue
        if not duty or not re.search(r"会长|副会长|书记|秘书长|主任|理事", duty):
            continue
        if name in seen:
            continue

        seen.add(name)
        detail_url = ""
        candidate_url = urljoin(entry_url, str(link.get("href") or ""))
        if candidate_url.rstrip("/") != entry_url.rstrip("/"):
            detail_url = candidate_url
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "medium",
                "parser": "page_inline_chinafpa_visible_leader_links_v4",
                "selector_summary": "region=.leaderBoxR.fr；item=.bdNow>a[href]；姓名与职务按职务起始词边界分隔",
            }
        )

    if not rows:
        raise RuntimeError(
            "在线页面.leaderBoxR.fr .bdNow内未形成可验证的逐人姓名职务链接"
        )
    return rows


PAGE_RULE = {
    "rule_id": "0219",
    "page_type": "多人物详情合并页",
    "structure_group": "chinafpa_visible_leader_links",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "browser_dom",
    "parser": "page_inline_chinafpa_visible_leader_links_v4",
    "leader_region_selector": ".leaderBoxR.fr .bdNow",
    "name_selector": ".leaderBoxR.fr .bdNow > a[href]",
    "duty_selector": ".leaderBoxR.fr .bdNow > a[href]",
    "detail_link_selector": ".leaderBoxR.fr .bdNow > a[href]",
    "content_scope": {
        "start_anchor": "现任领导区域",
        "end_anchor": "现任领导区域结束",
        "include_selectors": [".leaderBoxR.fr .bdNow"],
        "exclude_selectors": ["script", "style", "nav", "footer"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_item_dynamic_link",
        "detail_collector_type": "online",
        "detail_link_selector": ".leaderBoxR.fr .bdNow > a[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 20,
    },
    "risk_flag": "官网TLS需浏览器渲染；桌面端与移动端存在重复领导列表，仅解析可见桌面端.fr列表",
    "confidence": "high",
    "profile_reusable": "否",
    "profile_judgement": "在线不可达或结构不明确时安全失败",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".leaderBoxR.fr .bdNow",
            "name_selector": ".leaderBoxR.fr .bdNow > a[href]",
            "duty_selector": ".leaderBoxR.fr .bdNow > a[href]",
            "detail_link_selector": ".leaderBoxR.fr .bdNow > a[href]",
            "content_scope": {
                "start_anchor": "现任领导区域",
                "end_anchor": "现任领导区域结束",
                "include_selectors": [".leaderBoxR.fr .bdNow"],
                "exclude_selectors": ["script", "style", "nav", "footer"],
            },
        },
        "api": {"enabled": False, "reason": "未发现可跨会话复现且可验证的公开领导接口"},
    },
    "migration": {
        "source": "terminal_review_0219",
        "verified_status": "online_playwright_verified",
        "behavior_changed": True,
    },
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
