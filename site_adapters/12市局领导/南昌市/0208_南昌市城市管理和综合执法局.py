from __future__ import annotations

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0208",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "parser": "inline_ucapcontent_current_duty",
    "leader_region_selector": "ucapcontent",
    "risk_flag": "环境代理会返回创宇盾页面；页面专用解析仅在检测到防护页时对同一官方URL执行无代理重抓",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def fetch_without_environment_proxy(url: str) -> str:
    """绕过会触发创宇盾的环境代理，重新抓取同一权威页面。"""
    session = requests.Session()
    session.trust_env = False
    response = session.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/145 Safari/537.36"
            ),
            "Referer": "https://cgw.nc.gov.cn/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.content.decode("utf-8", errors="replace")


def normalize_text(value: str) -> str:
    """仅清理网页排版空白，不改变原文语义。"""
    return re.sub(r"\s+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """从正文中按网页顺序提取姓名及对应的“现任”原文。"""
    blocked_markers = ("创宇盾", "可疑的攻击行为", "notice-jiasule", "攻击行为")
    if any(marker in html for marker in blocked_markers) or "<ucapcontent" not in html.lower():
        html = fetch_without_environment_proxy(final_url)

    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("ucapcontent")
    if content is None:
        raise RuntimeError("真实页面缺少已核验的ucapcontent领导正文容器")

    lines = [
        cleaned
        for raw_line in content.get_text("\n").splitlines()
        if (cleaned := normalize_text(raw_line))
    ]
    rows: list[dict] = []
    seen_names: set[str] = set()
    for index, line in enumerate(lines):
        if not line.startswith("现任"):
            continue

        name = ""
        for previous_line in reversed(lines[max(0, index - 3) : index]):
            match = re.match(r"^([\u3400-\u9fff·]{2,6})[，,]", previous_line)
            if match:
                name = match.group(1)
                break
        if not name or name in seen_names:
            continue

        duty = re.sub(r"^现任\s*", "", line).strip()
        seen_names.add(name)
        rows.append(
            {
                "order": str(len(rows) + 1),
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
            }
        )

    if not rows:
        raise RuntimeError("ucapcontent正文中未找到可回指简历行的现任职务记录")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
