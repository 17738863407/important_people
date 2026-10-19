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
    "rule_id": "4176",
    "page_type": "院领导列表转个人主页",
    "structure_group": "naes_leader_cards_and_profile_duty",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "parser": "page_inline_naes_leader_profiles_v1",
    "leader_region_selector": "a.hoverblock",
    "name_selector": "a.hoverblock span",
    "duty_selector": "个人主页 li 中的职务字段",
    "detail_link_selector": "a.hoverblock[href]",
    "detail_strategy": {"required": True, "mode": "meta_refresh_to_profile_home"},
    "risk_flag": "列表链接先进入meta refresh过渡页；必须动态跟随到个人主页，并只读取明确的职务字段。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按列表顺序进入当前个人主页并抽取职务字段。"""
    import requests
    from bs4 import BeautifulSoup, Tag

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("a.hoverblock[href]")
    if not cards:
        raise RuntimeError("院领导列表未发现人物卡片")

    session = requests.Session()
    session.trust_env = False
    rows: list[dict] = []
    for card in cards:
        name = clean_text(card.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        transition_url = urljoin(final_url, card.get("href", ""))
        transition = session.get(transition_url, timeout=30)
        transition.raise_for_status()
        transition.encoding = transition.apparent_encoding or "utf-8"
        transition_soup = BeautifulSoup(transition.text, "html.parser")
        refresh = next(
            (
                node
                for node in transition_soup.select("meta[http-equiv]")
                if str(node.get("http-equiv", "")).lower() == "refresh"
            ),
            None,
        )
        refresh_content = refresh.get("content", "") if isinstance(refresh, Tag) else ""
        refresh_match = re.search(r"url\s*=\s*(.+)$", refresh_content, flags=re.I)
        profile_url = urljoin(transition.url, refresh_match.group(1).strip()) if refresh_match else transition.url

        profile = session.get(profile_url, timeout=30)
        profile.raise_for_status()
        profile.encoding = profile.apparent_encoding or "utf-8"
        profile_soup = BeautifulSoup(profile.text, "html.parser")
        duty = ""
        for item in profile_soup.find_all("li"):
            text = clean_text(item.get_text(" ", strip=True))
            if text.startswith("职务：") or text.startswith("职务:"):
                duty = clean_text(re.sub(r"^职务\s*[：:]", "", text))
                break
        if not duty:
            raise RuntimeError(f"个人主页未找到职务字段：{name}")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": profile.url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": "list=a.hoverblock；detail=meta refresh target；duty=li职务字段",
            }
        )

    if not rows:
        raise RuntimeError("院领导个人主页未抽取到有效人物")
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
