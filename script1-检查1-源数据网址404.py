from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
import html
from pathlib import Path
import re
import time
from typing import Any

import requests
from requests import Response
from requests.exceptions import RequestException
from tqdm import tqdm

from crawler_core.rule_table import load_rule_table
from crawler_core.paths import resolve_path_argument


@dataclass(frozen=True)
class SourceUrlRecord:
    """保存V3规则主表中某一行网址的来源信息，便于回表定位。"""

    sheet_name: str
    row_number: int
    rule_id: str
    organization: str
    original_url: str
    normalized_url: str


@dataclass(frozen=True)
class UrlCheckResult:
    """保存单个唯一网址的联网检查结果。"""

    normalized_url: str
    status_label: str
    http_status: str
    request_method: str
    final_url: str
    redirect_count: int
    elapsed_ms: int
    response_bytes: int
    content_type: str
    page_title: str
    review_note: str
    error_type: str
    error_message: str


class DualLogger:
    """同时向控制台和日志文件写入信息。"""

    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def info(self, message: str) -> None:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{current_time}] {message}"
        print(line)
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(line + "\n")


def normalize_url(raw_url: Any) -> str:
    """清洗单元格中的网址；缺少协议时默认补充 http://。"""
    url = str(raw_url or "").strip()
    if not url:
        return ""
    url = url.replace("\u3000", "").strip()
    if re.match(r"^https?://", url, flags=re.IGNORECASE):
        return url
    if re.match(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}(/.*)?$", url):
        return "http://" + url
    return url


def read_source_url_records(
    rule_table_path: Path,
    max_rows: int | None,
    logger: DualLogger,
) -> list[SourceUrlRecord]:
    """从V3唯一权威规则主表读取所有含依据链接的记录。"""
    records: list[SourceUrlRecord] = []
    empty_url_count = 0
    for row_number, record in enumerate(load_rule_table(rule_table_path), start=2):
        original_url = str(record.get("领导链接", "")).strip()
        normalized_url = normalize_url(original_url)
        if not normalized_url:
            empty_url_count += 1
            continue
        records.append(
            SourceUrlRecord(
                sheet_name=rule_table_path.name,
                row_number=row_number,
                rule_id=str(record.get("脚本序号", "")).strip(),
                organization=str(record.get("机构名称", "")).strip(),
                original_url=original_url,
                normalized_url=normalized_url,
            )
        )
        if max_rows is not None and len(records) >= max_rows:
            logger.info(f"已达到最大读取行数：{max_rows}")
            break

    logger.info(f"规则主表含网址记录：{len(records)}")
    logger.info(f"跳过空依据链接记录：{empty_url_count}")
    return records


def build_request_headers() -> dict[str, str]:
    """构造较接近普通浏览器的请求头，减少部分站点误拦截。"""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "close",
    }


def classify_status(status_code: int | None, error_type: str) -> str:
    """将 HTTP 状态码和异常类型归类为便于筛选的中文标签。"""
    if status_code == 404:
        return "404"
    if status_code == 410:
        return "410"
    if status_code is None:
        return "请求失败" if error_type else "未知"
    if 200 <= status_code < 400:
        return "正常"
    if 400 <= status_code < 500:
        return "客户端错误"
    if 500 <= status_code < 600:
        return "服务器错误"
    return "其他状态"


def extract_page_title(response: Response) -> str:
    """从 HTML 响应中提取标题，便于人工判断是否为错误页。"""
    content_type = response.headers.get("Content-Type", "")
    if "html" not in content_type.lower():
        return ""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", response.text, flags=re.IGNORECASE | re.DOTALL)
    if not title_match:
        return ""
    title = re.sub(r"\s+", " ", title_match.group(1)).strip()
    return html.unescape(title)


def build_review_note(status_code: int, response_bytes: int, page_title: str, response_text: str) -> str:
    """根据状态码和页面内容给出人工复核提示。"""
    title_text = page_title.lower()
    sample_text = response_text[:3000].lower()
    explicit_error_words = ["404", "not found", "出错", "找不到", "不存在", "error"]
    has_explicit_error = any(word in title_text or word in sample_text for word in explicit_error_words)

    if status_code == 404:
        if response_bytes == 0:
            return "HTTP 404，且响应正文为空，倾向真实失效"
        if has_explicit_error:
            return "HTTP 404，页面内容也呈现错误页，倾向真实失效"
        return "HTTP 404，但返回了非空页面内容；浏览器可能可显示，建议人工复核"
    if 400 <= status_code < 500:
        return "客户端错误状态，可能是权限、反爬或链接失效"
    if 500 <= status_code < 600:
        return "服务器错误状态，可能是临时故障，建议稍后复查"
    return ""


def response_to_result(response: Response, method: str, elapsed_ms: int) -> UrlCheckResult:
    """将 requests 响应对象转换为统一结果。"""
    content_type = response.headers.get("Content-Type", "")
    response_bytes = len(response.content or b"")
    page_title = extract_page_title(response=response)
    review_note = build_review_note(
        status_code=response.status_code,
        response_bytes=response_bytes,
        page_title=page_title,
        response_text=response.text if "html" in content_type.lower() else "",
    )
    return UrlCheckResult(
        normalized_url=response.request.url,
        status_label=classify_status(response.status_code, ""),
        http_status=str(response.status_code),
        request_method=method,
        final_url=response.url,
        redirect_count=len(response.history),
        elapsed_ms=elapsed_ms,
        response_bytes=response_bytes,
        content_type=content_type,
        page_title=page_title,
        review_note=review_note,
        error_type="",
        error_message="",
    )


def request_once(
    url: str,
    method: str,
    timeout_seconds: int,
    verify_ssl: bool,
    use_system_proxy: bool,
) -> tuple[Response, int]:
    """执行一次 HTTP 请求，并记录耗时。"""
    session = requests.Session()
    session.trust_env = use_system_proxy
    request_function = session.head if method == "HEAD" else session.get
    start_time = time.perf_counter()
    response = request_function(
        url,
        headers=build_request_headers(),
        allow_redirects=True,
        timeout=timeout_seconds,
        verify=verify_ssl,
    )
    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    response.close()
    return response, elapsed_ms


def check_single_url(
    url: str,
    timeout_seconds: int,
    retry_times: int,
    verify_ssl: bool,
    use_system_proxy: bool,
    fallback_get_status_codes: set[int],
) -> UrlCheckResult:
    """检查单个网址；先 HEAD，遇到异常或疑似误判时再 GET 复核。"""
    last_error_type = ""
    last_error_message = ""

    for attempt_index in range(retry_times + 1):
        try:
            response, elapsed_ms = request_once(
                url=url,
                method="HEAD",
                timeout_seconds=timeout_seconds,
                verify_ssl=verify_ssl,
                use_system_proxy=use_system_proxy,
            )
            if response.status_code not in fallback_get_status_codes:
                return response_to_result(response=response, method="HEAD", elapsed_ms=elapsed_ms)
        except RequestException as error:
            last_error_type = error.__class__.__name__
            last_error_message = str(error)

        try:
            response, elapsed_ms = request_once(
                url=url,
                method="GET",
                timeout_seconds=timeout_seconds,
                verify_ssl=verify_ssl,
                use_system_proxy=use_system_proxy,
            )
            return response_to_result(response=response, method="GET", elapsed_ms=elapsed_ms)
        except RequestException as error:
            last_error_type = error.__class__.__name__
            last_error_message = str(error)

        if attempt_index < retry_times:
            time.sleep(1)

    return UrlCheckResult(
        normalized_url=url,
        status_label=classify_status(None, last_error_type),
        http_status="",
        request_method="HEAD+GET",
        final_url="",
        redirect_count=0,
        elapsed_ms=0,
        response_bytes=0,
        content_type="",
        page_title="",
        review_note="请求失败，未取得 HTTP 状态码",
        error_type=last_error_type,
        error_message=last_error_message.replace("\r", " ").replace("\n", " "),
    )


def check_unique_urls(
    urls: list[str],
    timeout_seconds: int,
    retry_times: int,
    verify_ssl: bool,
    use_system_proxy: bool,
    fallback_get_status_codes: set[int],
    workers: int,
) -> dict[str, UrlCheckResult]:
    """并发检查去重后的网址，单个网址失败不会中断整体任务。"""
    results: dict[str, UrlCheckResult] = {}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_url = {
            executor.submit(
                check_single_url,
                url,
                timeout_seconds,
                retry_times,
                verify_ssl,
                use_system_proxy,
                fallback_get_status_codes,
            ): url
            for url in urls
        }

        for future in tqdm(as_completed(future_to_url), total=len(future_to_url), desc="检查网址"):
            url = future_to_url[future]
            try:
                results[url] = future.result()
            except Exception as error:
                results[url] = UrlCheckResult(
                    normalized_url=url,
                    status_label="脚本异常",
                    http_status="",
                    request_method="",
                    final_url="",
                    redirect_count=0,
                    elapsed_ms=0,
                    response_bytes=0,
                    content_type="",
                    page_title="",
                    review_note="脚本内部异常，需排查错误信息",
                    error_type=error.__class__.__name__,
                    error_message=str(error).replace("\r", " ").replace("\n", " "),
                )

    return results


def should_export_result(status_label: str, only_problem_rows: bool) -> bool:
    """控制是否只导出问题链接。"""
    if not only_problem_rows:
        return True
    return status_label != "正常"


def build_report_sort_key(record: SourceUrlRecord, result: UrlCheckResult) -> tuple[int, int, str, str, int]:
    """按 HTTP 状态码排序；无状态码的异常排在有状态码记录之后。"""
    if result.http_status.isdigit():
        status_group = 0
        status_code = int(result.http_status)
    else:
        status_group = 1
        status_code = 999999
    return (status_group, status_code, result.status_label, record.sheet_name, record.row_number)


def write_report(
    report_path: Path,
    records: list[SourceUrlRecord],
    results: dict[str, UrlCheckResult],
    only_problem_rows: bool,
) -> int:
    """将检查结果导出为制表符分隔的 txt 文件。"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "检查时间",
        "判定",
        "HTTP状态",
        "请求方法",
        "源文件",
        "源行号",
        "脚本序号",
        "机构",
        "原始网址",
        "最终网址",
        "重定向次数",
        "响应毫秒",
        "响应字节数",
        "内容类型",
        "页面标题",
        "复核说明",
        "错误类型",
        "错误信息",
    ]
    export_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    exported_count = 0
    report_rows: list[tuple[tuple[int, int, str, str, int], list[str]]] = []

    for record in records:
        result = results.get(record.normalized_url)
        if result is None:
            continue
        if not should_export_result(result.status_label, only_problem_rows):
            continue

        row = [
            export_time,
            result.status_label,
            result.http_status,
            result.request_method,
            record.sheet_name,
            str(record.row_number),
            record.rule_id,
            record.organization,
            record.original_url,
            result.final_url,
            str(result.redirect_count),
            str(result.elapsed_ms),
            str(result.response_bytes),
            result.content_type,
            result.page_title,
            result.review_note,
            result.error_type,
            result.error_message,
        ]
        clean_row = [value.replace("\t", " ").replace("\r", " ").replace("\n", " ") for value in row]
        report_rows.append((build_report_sort_key(record=record, result=result), clean_row))

    with report_path.open("w", encoding="utf-8") as file:
        file.write("\t".join(headers) + "\n")
        for _, clean_row in sorted(report_rows, key=lambda item: item[0]):
            file.write("\t".join(clean_row) + "\n")
            exported_count += 1

    return exported_count


def summarize_results(records: list[SourceUrlRecord], results: dict[str, UrlCheckResult]) -> dict[str, int]:
    """按判定标签统计结果数量。"""
    summary: dict[str, int] = {}
    for record in records:
        result = results.get(record.normalized_url)
        label = result.status_label if result else "未检查"
        summary[label] = summary.get(label, 0) + 1
    return summary


def main(
    rule_table_path: str | Path,
    report_path: str | Path,
    log_path: str | Path,
    timeout_seconds: int,
    retry_times: int,
    verify_ssl: bool,
    use_system_proxy: bool,
    fallback_get_status_codes: set[int],
    workers: int,
    only_problem_rows: bool,
    max_rows: int | None,
) -> None:
    """读取V3规则主表网址，检查HTTP状态，并输出可回溯报告。"""
    rule_table_path = resolve_path_argument(
        rule_table_path, anchor=__file__, must_exist=True
    )
    report_path = resolve_path_argument(report_path, anchor=__file__)
    log_path = resolve_path_argument(log_path, anchor=__file__)
    logger = DualLogger(log_path=log_path)
    logger.info(f"开始读取V3权威规则主表：{rule_table_path}")
    records = read_source_url_records(
        rule_table_path=rule_table_path,
        max_rows=max_rows,
        logger=logger,
    )
    unique_urls = sorted({record.normalized_url for record in records})
    logger.info(f"源数据含网址行数：{len(records)}")
    logger.info(f"去重后待检查网址数：{len(unique_urls)}")

    results = check_unique_urls(
        urls=unique_urls,
        timeout_seconds=timeout_seconds,
        retry_times=retry_times,
        verify_ssl=verify_ssl,
        use_system_proxy=use_system_proxy,
        fallback_get_status_codes=fallback_get_status_codes,
        workers=workers,
    )
    exported_count = write_report(
        report_path=report_path,
        records=records,
        results=results,
        only_problem_rows=only_problem_rows,
    )
    summary = summarize_results(records=records, results=results)

    for label, count in sorted(summary.items(), key=lambda item: item[0]):
        logger.info(f"结果统计：{label} = {count}")
    logger.info(f"已导出报告行数：{exported_count}")
    logger.info(f"报告路径：{report_path}")
    logger.info(f"日志路径：{log_path}")


if __name__ == "__main__":
    current_time_value = datetime.now().strftime("%Y%m%d_%H%M%S")
    rule_table_path_value = r"important_people/workspace/source_data/规则主表.txt"
    report_path_value = rf"important_people/workspace/reports/源数据网址状态检查_{current_time_value}.txt"
    log_path_value = rf"important_people/workspace/log/源数据网址状态检查_{current_time_value}.log"
    timeout_seconds_value = 8
    retry_times_value = 0
    verify_ssl_value = True
    use_system_proxy_value = False
    fallback_get_status_codes_value = {400, 403, 404, 405, 406, 410, 429, 500, 501, 503}
    workers_value = 48
    only_problem_rows_value = True
    max_rows_value = None
    main(
        rule_table_path=rule_table_path_value,
        report_path=report_path_value,
        log_path=log_path_value,
        timeout_seconds=timeout_seconds_value,
        retry_times=retry_times_value,
        verify_ssl=verify_ssl_value,
        use_system_proxy=use_system_proxy_value,
        fallback_get_status_codes=fallback_get_status_codes_value,
        workers=workers_value,
        only_problem_rows=only_problem_rows_value,
        max_rows=max_rows_value,
    )
