from __future__ import annotations

import html as html_lib
import json
import re
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from crawler_core.models import PersonRecord


PARSER_NAME = "S_HARBIN_GOV_CN_LEADER_API_V1"


def configure_harbin_gov_cn_leader_api(page_rule: dict[str, Any], channel_id: str) -> None:
    """配置哈尔滨市政府信息公开领导接口。"""
    page_rule["fetch_mode"] = str(page_rule.get("fetch_mode") or "snapshot")
    page_rule["parser"] = PARSER_NAME
    page_rule["locator_strategy"] = "custom_parse_page"
    page_rule["confidence"] = "high"
    page_rule["profile_reusable"] = "harbin_gov_cn_leader_api"
    page_rule["profile_judgement"] = "哈尔滨市政府信息公开领导页同构，领导数据来自 common/search/{channelId} JSON。"
    page_rule["harbin_leader_channel_id"] = channel_id
    locator = page_rule.setdefault("locator", {})
    locator["api"] = {"enabled": True, "endpoint": "/common/search/{channelId}", "channel_id": channel_id}
    locator["migration"] = {"source": "harbin_gov_cn_leader_api_profile", "verified_status": "fixed", "behavior_changed": True}


def parse_harbin_gov_cn_leader_api_page(html: str, final_url: str, page_rule: dict[str, Any]) -> list[PersonRecord]:
    """从哈尔滨 common/search 领导接口解析姓名和职务。"""
    channel_id = str(page_rule.get("harbin_leader_channel_id") or "").strip()
    if not channel_id:
        return []
    data = _fetch_api(channel_id)
    results = ((data.get("data") or {}).get("results") or []) if isinstance(data, dict) else []
    rows: list[PersonRecord] = []
    seen: set[str] = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        raw_title = _clean_text(str(item.get("title") or ""))
        name, duty = _parse_title(raw_title)
        content_text = _html_to_text(str(item.get("contentHtml") or ""))
        if not name:
            name = _clean_name(raw_title)
        if not duty:
            duty = _parse_content_duty(content_text, name)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            PersonRecord(
                organization=str(page_rule.get("organization") or ""),
                url=str(page_rule.get("url") or final_url),
                name=name,
                duty=duty,
                detail_url=str(item.get("url") or ""),
                evidence=f"{name}：{duty}",
                confidence="high",
                parser=PARSER_NAME,
                selector_summary=f"api=/common/search/{channel_id}; title/contentHtml",
            )
        )
    return rows


def _fetch_api(channel_id: str) -> dict[str, Any]:
    query = urlencode(
        {
            "_isAgg": "false",
            "_isJson": "true",
            "_pageSize": "50",
            "_template": "index",
            "_rangeTimeGte": "",
            "_channelName": "",
            "page": "1",
        }
    )
    url = f"https://www.harbin.gov.cn/common/search/{channel_id}?{query}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.harbin.gov.cn/"})
    with urlopen(request, timeout=25) as response:
        payload = response.read().decode("utf-8", errors="ignore")
    return json.loads(payload)


def _parse_title(title: str) -> tuple[str, str]:
    match = re.match(r"^(?P<name>[\u4e00-\u9fff·\s&nbsp;]{2,12})[:：](?P<duty>.+)$", title)
    if not match:
        return "", ""
    name = _clean_name(match.group("name"))
    duty = _clean_text(match.group("duty"))
    return name, duty


def _parse_content_duty(content_text: str, name: str) -> str:
    if not content_text:
        return ""
    if name and content_text.startswith(f"{name}："):
        content_text = content_text.split("：", 1)[1]
    elif name and content_text.startswith(f"{name}:"):
        content_text = content_text.split(":", 1)[1]
    sentence = re.split(r"[。；;]", content_text, maxsplit=1)[0]
    return _clean_text(sentence)


def _html_to_text(value: str) -> str:
    soup = BeautifulSoup(value, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    return _clean_text(soup.get_text(" ", strip=True))


def _clean_name(value: str) -> str:
    text = html_lib.unescape(value or "").replace("\xa0", " ")
    return re.sub(r"\s+", "", text).strip(" ：:")


def _clean_text(value: str) -> str:
    text = html_lib.unescape(value or "").replace("\xa0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip(" ：:\t\r\n")
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return re.sub(r"(?<=[，、；：])\s+(?=[\u4e00-\u9fff])", "", text)
