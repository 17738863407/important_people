from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


PAGE_RULE = {
    "rule_id": "0844",
    "page_type": "人物目录详情页",
    "structure_group": "nmg_sasac_agency_profile_leader_groups_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态XHR返回HTML片段",
    "fetch_mode": "requests",
    "extract_mode": "page_local_parse_page",
    "collector": "static_http",
    "parser": "page_local_parse_page",
    "leader_region_selector": "机关简介片段内两个领导简介分组的.leaderList",
    "name_selector": "li 内第二个 p",
    "duty_selector": "li 内第一个 p",
    "detail_link_selector": "li a[href]",
    "risk_flag": "规则入口以jQuery.load载入机关简介片段，必须排除委内处室和所属事业单位",
    "confidence": "high",
}


def _clean_text(value: str) -> str:
    """确定性压缩网页排版空白。"""
    return re.sub(r"\s+", " ", value).strip()


def _clean_name(value: str) -> str:
    """姓名仅移除网页排版空白。"""
    return re.sub(r"\s+", "", value)


def _build_session() -> requests.Session:
    """建立带有限GET重试的同站会话。"""
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _request_soup(session: requests.Session, url: str) -> tuple[BeautifulSoup, str]:
    """请求静态页面或HTML片段。"""
    response = session.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return BeautifulSoup(response.text, "html.parser"), response.url


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """动态发现机关简介片段，解析两个明确领导分组并核验详情页。"""
    del page_rule
    entry_soup = BeautifulSoup(html, "html.parser")
    profile_anchor = None
    for anchor in entry_soup.find_all("a", attrs={"data-url": True}):
        data_url = str(anchor["data-url"])
        if (
            _clean_text(anchor.get_text(" ", strip=True)) == "机关简介"
            or data_url.rstrip("/").endswith("/jgjj")
        ):
            profile_anchor = anchor
            break
    if profile_anchor is None:
        profile_url = urljoin(final_url, "/zfxxgk/zfxxgkml/jgjj/")
    else:
        profile_url = urljoin(final_url, str(profile_anchor["data-url"]))
    session = _build_session()
    profile_soup, profile_final_url = _request_soup(session, profile_url)

    accepted_groups = {
        "自治区国资委领导简介",
        "自治区纪委监委驻国资委纪检监察组领导简介",
    }
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    seen_details: set[str] = set()
    matched_groups: set[str] = set()

    for title in profile_soup.select(".main_box > .qgl_system_title > h3"):
        group_title = _clean_text(title.get_text(" ", strip=True))
        if group_title not in accepted_groups:
            continue
        matched_groups.add(group_title)
        leader_list = title.parent.find_next_sibling("div", class_="leaderList")
        if leader_list is None:
            raise ValueError(f"领导分组缺少人物列表：{group_title}")
        for item in leader_list.select("ul > li"):
            paragraphs = item.find_all("p")
            detail_anchor = item.find("a", href=True)
            if len(paragraphs) < 2 or detail_anchor is None:
                raise ValueError(f"领导卡片字段不完整：{group_title}")
            duty = _clean_text(paragraphs[0].get_text(" ", strip=True))
            name = _clean_name(paragraphs[1].get_text(" ", strip=True))
            if not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
                raise ValueError(f"领导卡片姓名职务异常：{group_title}")
            if name in seen_names:
                raise ValueError(f"领导分组出现重复姓名：{name}")

            detail_url = urljoin(profile_final_url, detail_anchor["href"])
            detail_soup, detail_final_url = _request_soup(session, detail_url)
            detail_text = _clean_name(detail_soup.get_text(" ", strip=True))
            if name not in detail_text:
                raise ValueError(f"人物详情页无法回指姓名：{detail_final_url}")
            if detail_final_url in seen_details:
                raise ValueError(f"多名人物复用了同一详情页：{detail_final_url}")

            seen_names.add(name)
            seen_details.add(detail_final_url)
            rows.append({"name": name, "duty": duty, "detail_url": detail_final_url})

    if matched_groups != accepted_groups:
        missing = "、".join(sorted(accepted_groups - matched_groups))
        raise ValueError(f"机关简介缺少预期领导分组：{missing}")
    if not rows:
        raise ValueError("两个领导简介分组均未发现人物卡片")
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
