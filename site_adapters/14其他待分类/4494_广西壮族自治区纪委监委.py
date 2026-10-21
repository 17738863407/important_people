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
    "rule_id": "4494",
    "page_type": "纪委监委领导入口转两篇强结构文章",
    "structure_group": "guangxi_discipline_supervision_articles_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML入口及静态详情文章",
    "extract_mode": "list_to_detail",
    "parser": "page_guangxi_discipline_supervision_articles_v1",
    "leader_region_selector": ".more_list .m_textlist",
    "name_selector": ".content p中的允许角色名单",
    "duty_selector": ".content p > strong角色标签与文章标题主体",
    "detail_link_selector": "",
    "detail_strategy": {"required": True, "mode": "dynamic_shared_articles", "max_detail_links": 2},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "入口同时链接纪委与监委文章；只保留纪委书记、副书记、常务委员及监委主任、副主任，排除纪委委员名单和监委委员；多人共用文章不作为人物详情页。",
}


def clean_text(value: str) -> str:
    """合并页面排版空白，不改变正文语义。"""
    return re.sub(r"[\s\u2000-\u200f\u202a-\u202e\u2060\u3000\xa0]+", " ", value or "").strip()


def discover_article_urls(html: str, final_url: str) -> list[tuple[str, str]]:
    """按入口列表顺序发现纪委、监委两篇当前领导文章。"""
    soup = BeautifulSoup(html or "", "html.parser")
    expected_titles = {
        "中国共产党广西壮族自治区第十二届纪律检查委员会": "discipline",
        "广西壮族自治区监察委员会": "supervision",
    }
    discovered: dict[str, str] = {}
    for link in soup.select(".more_list .m_textlist a[href]"):
        title = clean_text(link.get_text(" ", strip=True))
        kind = expected_titles.get(title)
        if kind and kind not in discovered:
            discovered[kind] = urljoin(final_url, str(link.get("href") or "").strip())
    missing = [kind for kind in ("discipline", "supervision") if kind not in discovered]
    if missing:
        raise RuntimeError(f"领导入口缺少当前文章：{','.join(missing)}")
    return [(kind, discovered[kind]) for kind in ("discipline", "supervision")]


def extract_names(value: str) -> list[str]:
    """从同一角色段落按页面顺序提取姓名，并删除民族等括注。"""
    names: list[str] = []
    for token in re.split(r"[\s\u3000\xa0]+", clean_text(value)):
        name = re.sub(r"（[^）]*）|\([^)]*\)", "", token).replace(" ", "").strip("，,、；;：:")
        if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            names.append(name)
    return names


def extract_role_rows(html: str, kind: str) -> list[tuple[str, str]]:
    """从详情正文提取允许角色，完整保留文章标题所示任职主体。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(".article .content")
    if region is None:
        raise RuntimeError(f"{kind}文章未找到正文区域 .article .content")
    allowed_roles = {
        "discipline": {"书记", "副书记", "常务委员"},
        "supervision": {"主任", "副主任"},
    }[kind]
    rows: list[tuple[str, str]] = []
    for paragraph in region.select("p"):
        label_node = paragraph.select_one("strong")
        if label_node is None:
            continue
        label = re.sub(r"[\s：:]", "", label_node.get_text(" ", strip=True))
        if label not in allowed_roles:
            continue
        paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
        label_text = clean_text(label_node.get_text(" ", strip=True))
        names_text = paragraph_text.replace(label_text, "", 1).lstrip("：: ")
        subject = (
            "中国共产党广西壮族自治区第十二届纪律检查委员会"
            if kind == "discipline"
            else "广西壮族自治区监察委员会"
        )
        duty = f"{subject}{label}"
        for name in extract_names(names_text):
            rows.append((name, duty))
    if not rows:
        raise RuntimeError(f"{kind}文章未提取到允许角色记录")
    return rows


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """在线抓取两篇当前文章，按首次出现顺序合并同人允许职务。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    ordered_names: list[str] = []
    duties_by_name: dict[str, list[str]] = {}
    for kind, article_url in discover_article_urls(html, final_url):
        detail = fetch_html_with_strategy(article_url, strategy="requests", timeout=30, referer=final_url)
        for name, duty in extract_role_rows(detail.html, kind):
            if name not in duties_by_name:
                duties_by_name[name] = []
                ordered_names.append(name)
            if duty not in duties_by_name[name]:
                duties_by_name[name].append(duty)

    return [
        {
            "name": name,
            "duty": "；".join(duties_by_name[name]),
            "evidence": "；".join(duties_by_name[name]),
            "detail_url": "",
            "confidence": "high",
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": "入口两篇当前文章；正文strong角色标签；允许角色；按首次文章与段落顺序合并",
        }
        for name in ordered_names
    ]


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
