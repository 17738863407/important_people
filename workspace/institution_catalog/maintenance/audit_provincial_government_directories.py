"""抓取并审计31个省级政府机构目录页，保存可复核的原始HTML。"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from crawler_core.paths import resolve_project_path


def configure_logging(log_path: Path) -> logging.Logger:
    """同时配置控制台与UTF-8日志文件。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("provincial_government_directory_audit")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s\t%(levelname)s\t%(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def read_bookmark_folder(bookmark_path: Path, folder_name: str) -> list[tuple[str, str]]:
    """从Netscape书签HTML的指定文件夹读取直属链接。"""
    soup = BeautifulSoup(bookmark_path.read_text(encoding="utf-8"), "html.parser")
    folder_heading = next(
        (heading for heading in soup.find_all("h3") if heading.get_text(strip=True) == folder_name),
        None,
    )
    if folder_heading is None:
        raise ValueError(f"书签中未找到文件夹：{folder_name}")
    folder_list = folder_heading.find_next("dl")
    if folder_list is None:
        raise ValueError(f"书签文件夹缺少链接列表：{folder_name}")
    return [
        (anchor.get_text(" ", strip=True), anchor.get("href", "").strip())
        for anchor in folder_list.find_all("a")
        if anchor.get("href", "").strip()
    ]


def safe_file_stem(index: int, label: str, url: str) -> str:
    """生成不会携带URL特殊字符的HTML快照文件名。"""
    clean_label = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", label).strip(" ._")
    host = urlparse(url).netloc.replace(":", "_")
    return f"{index:02d}_{clean_label}_{host}"


def request_page(url: str, timeout_seconds: int) -> tuple[requests.Response, str]:
    """优先使用环境网络配置，失败后仅在当前进程内改用直连重试。"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
    }
    first_error = ""
    for use_environment in (True, False):
        session = requests.Session()
        session.trust_env = use_environment
        try:
            response = session.get(url, headers=headers, timeout=timeout_seconds, allow_redirects=True)
            response.raise_for_status()
            return response, "environment" if use_environment else "direct"
        except requests.RequestException as exc:
            first_error = f"{first_error} | {exc}" if first_error else str(exc)
        finally:
            session.close()
    raise requests.RequestException(first_error)


def decode_response(response: requests.Response) -> str:
    """结合HTTP头、页面声明和统计结果解码中文政府网站页面。"""
    if response.encoding and response.encoding.lower() not in {"iso-8859-1", "ascii"}:
        return response.text
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def summarize_html(html: str) -> tuple[str, list[str], int]:
    """提取标题、疑似机构分类标题及链接总数，供后续选择解析策略。"""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    category_pattern = re.compile(
        r"(办公厅|组成部门|直属特设机构|直属机构|部门管理机构|派出机构|议事协调机构|事业单位|工作部门)"
    )
    categories: list[str] = []
    for node in soup.find_all(["h1", "h2", "h3", "h4", "h5", "strong", "dt", "span", "div", "li"]):
        text = re.sub(r"\s+", "", node.get_text(" ", strip=True))
        if 2 <= len(text) <= 30 and category_pattern.search(text) and text not in categories:
            categories.append(text)
    return title, categories[:30], len(soup.find_all("a", href=True))


def write_summary(summary_path: Path, rows: list[list[str]]) -> None:
    """将抓取摘要写成UTF-8制表符文本。"""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    header = ["序号", "区域书签名", "目录链接", "最终链接", "状态", "采集方式", "标题", "链接数", "疑似分类标题", "错误"]
    with summary_path.open("w", encoding="utf-8", newline="") as file:
        file.write("\t".join(header) + "\n")
        for row in rows:
            file.write("\t".join(cell.replace("\t", " ").replace("\r", " ").replace("\n", " ") for cell in row) + "\n")


def main(
    bookmark_path: Path,
    folder_name: str,
    snapshot_dir: Path,
    summary_path: Path,
    log_path: Path,
    timeout_seconds: int,
) -> None:
    """执行目录入口抓取、快照保存和摘要输出。"""
    logger = configure_logging(log_path)
    links = read_bookmark_folder(bookmark_path, folder_name)
    logger.info("读取书签目录成功：%s，共%d个入口", folder_name, len(links))
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    rows: list[list[str]] = []

    for index, (label, url) in enumerate(tqdm(links, desc="抓取省级政府机构目录", unit="站"), start=1):
        try:
            response, route = request_page(url, timeout_seconds)
            html = decode_response(response)
            snapshot_path = snapshot_dir / f"{safe_file_stem(index, label, url)}.html"
            snapshot_path.write_text(html, encoding="utf-8")
            title, categories, link_count = summarize_html(html)
            rows.append(
                [
                    str(index),
                    label,
                    url,
                    response.url,
                    str(response.status_code),
                    route,
                    title,
                    str(link_count),
                    " | ".join(categories),
                    "",
                ]
            )
            logger.info("成功：%02d %s，链接%d个，%s", index, label, link_count, response.url)
        except Exception as exc:
            rows.append([str(index), label, url, "", "", "", "", "0", "", str(exc)])
            logger.exception("失败：%02d %s %s", index, label, url)

    write_summary(summary_path, rows)
    success_count = sum(1 for row in rows if row[4])
    logger.info("抓取结束：成功%d/%d，摘要：%s", success_count, len(rows), summary_path)


if __name__ == "__main__":
    bookmark_path = resolve_project_path(r"important_people/workspace/source_data/机构目录/bookmarks_2026_9_1.html", anchor=__file__, must_exist=True)
    folder_name = "19.34个省级行政区政府机构"
    snapshot_dir = resolve_project_path(r"important_people/workspace/snapshots/机构目录/省级政府机构目录/html", anchor=__file__)
    summary_path = resolve_project_path(r"important_people/workspace/reports/机构目录/省级政府机构目录抓取摘要.txt", anchor=__file__)
    log_path = resolve_project_path(r"important_people/workspace/log/机构目录/省级政府机构目录抓取.log", anchor=__file__)
    timeout_seconds = 30
    main(bookmark_path, folder_name, snapshot_dir, summary_path, log_path, timeout_seconds)
