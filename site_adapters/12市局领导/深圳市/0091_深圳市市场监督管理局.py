from __future__ import annotations

import re
import sys
from pathlib import Path

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0091",
    "page_type": "接口跳转人物表格页",
    "structure_group": "gd_gkmlpt_leader_api_detail_v2",
    "reuse_scope": "gd_gkmlpt_same_structure",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "gd_gkmlpt_leader_api_detail_v2",
    "leader_region_selector": "政府信息公开平台分类接口articles数组",
    "name_selector": "jump_url页面.ldbox2-table tbody th[scope=row]",
    "duty_selector": "jump_url页面.ldbox2-table同行td",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "api_jump_to_table"},
    "api_config": {
        "url": "https://amr.sz.gov.cn/gkmlpt/api/all/903",
        "method": "GET",
        "params": {"page": 1, "sid": "755003"},
        "data_path": "articles",
        "name_field": "title",
        "detail_url_field": "url",
    },
    "risk_flag": "分类接口当前以jump_url指向静态领导表格；须动态读取跳转地址并保持表格行顺序",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML与接口字段中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def fetch_json(session: requests.Session, page_rule: dict) -> dict:
    """请求经页面脚本核实的机构领导分类接口。"""
    config = page_rule["api_config"]
    response = session.get(config["url"], params=config["params"], timeout=30)
    response.raise_for_status()
    data = response.json()
    classify = data.get("classify") or {}
    articles = data.get(config["data_path"])
    if classify.get("id") != 903 or classify.get("name") != "机构领导":
        raise RuntimeError("分类接口返回的栏目身份与机构领导不一致")
    if not isinstance(articles, list):
        raise RuntimeError("机构领导分类接口articles字段类型异常")
    jump_url = clean_text(str(classify.get("jump_url") or ""))
    if not articles and not jump_url.startswith("https://amr.sz.gov.cn/"):
        raise RuntimeError("机构领导分类接口既无人物数组也无可信跳转地址")
    if articles and data.get("total") != len(articles):
        raise RuntimeError("机构领导分类接口存在未获取的分页记录")
    return data


def fetch_detail(session: requests.Session, detail_url: str) -> str:
    """在线获取人物详情页。"""
    response = session.get(detail_url, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def extract_evidence(html: str, expected_name: str) -> str:
    """从详情正文提取强结构职务字段原文。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one(".article-content")
    if article is None:
        raise RuntimeError(f"详情页缺少 .article-content：{expected_name}")
    text = clean_text(article.get_text(" ", strip=True))
    if expected_name not in re.sub(r"\s+", "", text):
        raise RuntimeError(f"详情正文缺少接口姓名：{expected_name}")
    match = re.search(r"职务\s*[：:]\s*(.+?)(?=\s*工作分工\s*[：:]|$)", text)
    if match is None:
        raise RuntimeError(f"详情正文缺少职务字段：{expected_name}")
    evidence = clean_text(match.group(1)).strip("：:；;，,")
    if not evidence:
        raise RuntimeError(f"详情正文职务字段为空：{expected_name}")
    return evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按分类接口数组顺序逐页在线提取人物姓名、职务证据和详情链接。"""
    from crawler_core.models import PersonRecord

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": final_url})
    data = fetch_json(session, page_rule)
    config = page_rule["api_config"]
    records: list[object] = []
    seen_names: set[str] = set()
    seen_urls: set[str] = set()
    articles = data[config["data_path"]]
    if not articles:
        from bs4 import BeautifulSoup

        jump_url = clean_text(str(data["classify"].get("jump_url") or ""))
        response = session.get(jump_url, timeout=30)
        response.raise_for_status()
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
        tables = soup.select("table.ldbox2-table")
        if len(tables) != 1:
            raise RuntimeError(f"机构领导表格数量异常：{len(tables)}")
        for row in tables[0].select("tbody > tr"):
            name_node = row.select_one(':scope > th[scope="row"]')
            duty_node = row.select_one(":scope > td")
            name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
            evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
                raise RuntimeError("机构领导表格出现异常姓名或空职务")
            if name in seen_names:
                raise RuntimeError(f"机构领导表格人物重复：{name}")
            seen_names.add(name)
            records.append(
                PersonRecord(
                    organization=page_rule["organization"],
                    url=page_rule["url"],
                    name=name,
                    duty=evidence,
                    detail_url="",
                    evidence=evidence,
                    confidence="high",
                    parser=page_rule["parser"],
                )
            )
        if not records:
            raise RuntimeError("机构领导表格没有可验证人物记录")
        return records
    for item in articles:
        name = re.sub(r"\s+", "", clean_text(str(item.get(config["name_field"]) or "")))
        detail_url = clean_text(str(item.get(config["detail_url_field"]) or ""))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not detail_url.startswith("https://amr.sz.gov.cn/gkmlpt/content/"):
            raise RuntimeError("机构领导接口返回异常姓名或详情链接")
        if name in seen_names or detail_url in seen_urls:
            raise RuntimeError(f"机构领导接口人物或链接重复：{name}")
        evidence = extract_evidence(fetch_detail(session, detail_url), name)
        seen_names.add(name)
        seen_urls.add(detail_url)
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
