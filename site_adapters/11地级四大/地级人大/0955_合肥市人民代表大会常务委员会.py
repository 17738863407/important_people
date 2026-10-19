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


def clean_text(value: str) -> str:
    """清理网页标签内的排版空白。"""
    return re.sub(r"\s+", "", str(value or "").replace("\u3000", " ")).strip()


def fetch_commissioner_names(group: object, base_url: str) -> list[str]:
    """从委员分组动态引用的官方JS中按原序提取姓名。"""
    script = group.select_one("script[src*='/ljgl/lmylj/zrzc-wy/']")
    script_url = urljoin(base_url, str(script.get("src") or "")) if script else ""
    if not script_url:
        raise ValueError("委员分组未发现官方名单JS")

    session = requests.Session()
    session.trust_env = False
    response = session.get(
        script_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145 Safari/537.36",
            "Referer": base_url,
        },
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    names: list[str] = []
    for raw_name in re.findall(r'title="([^"]+)"', response.text):
        name = clean_text(raw_name)
        name = re.sub(r"[（(][^）)]*(?:女|族)[^）)]*[）)]$", "", name)
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            names.append(name)
    if not names:
        raise ValueError("官方委员名单JS未解析出姓名")
    return names


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按页面分组顺序解析主任、副主任和秘书长。"""
    soup = BeautifulSoup(html, "html.parser")
    groups = soup.select(".zr-list")
    if not groups:
        raise ValueError("未找到领导分组 .zr-list")

    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=.zr-list；"
        "duty=:scope > span；name=:scope > ul a[title][href]；detail=同一姓名链接"
    )
    for group in groups:
        duty_node = group.select_one(":scope > span")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").rstrip("：:")
        duty = re.sub(r"[（(]按姓名笔画为序排列[）)]", "", duty)
        if "zr-wylist" in (group.get("class") or []):
            continue
        if duty not in {"主任", "副主任", "秘书长"}:
            continue
        for link in group.select(":scope > ul a[href]"):
            name = clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                continue
            key = (name, duty)
            if key in seen:
                continue
            seen.add(key)
            detail_url = urljoin(base_url, str(link.get("href") or ""))
            rows.append(
                {
                    "order": str(len(rows) + 1),
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": detail_url,
                    "confidence": "high",
                    "parser": "page_inline_hefei_renda_all_groups_v2",
                    "selector_summary": selector_summary,
                }
            )

    if not rows:
        raise ValueError("页面领导分组未解析出有效人物")
    return rows


PAGE_RULE = {
    "rule_id": "0955",
    "page_type": "现任领导信息页",
    "structure_group": "hefei_renda_all_current_groups",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "role_group_direct",
    "collector": "static_http",
    "parser": "page_inline_hefei_renda_all_groups_v2",
    "leader_region_selector": ".zr-list",
    "name_selector": ":scope > ul a[title][href]",
    "duty_selector": ":scope > span",
    "detail_link_selector": ":scope > ul a[title][href]",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "按.zr-wylist页面专属类精确排除末尾委员分组，保留主任、副主任、秘书长领导分组",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".zr-list",
            "name_selector": ":scope > ul a[title][href]",
            "duty_selector": ":scope > span",
            "detail_link_selector": ":scope > ul a[title][href]",
        },
        "api": {
            "enabled": False,
            "reason": "现任领导分组、姓名、职务和人物页链接均在公开静态HTML中提供",
        },
        "migration": {
            "source": "failed_script_v3_task7",
            "verified_status": "online_verified_20260808",
            "behavior_changed": True,
        },
    },
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
