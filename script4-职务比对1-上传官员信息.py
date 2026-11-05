from __future__ import annotations

import os
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import TextIO
from unittest.mock import patch

import requests
from openpyxl import Workbook
from playwright.sync_api import sync_playwright

from crawler_core.paths import (
    find_chrome_executable,
    resolve_path_argument,
    timestamped_output_path,
)


EXPECTED_SOURCE_HEADER = [
    "姓名*",
    "职务*",
    "排序*",
    "职级*",
    "所属省*",
    "所属市",
    "依据链接",
    "依据说明",
    "维护人",
    "机构",
    "详情页链接",
    "脚本序号",
]


def write_log(message: str, log_file: TextIO) -> None:
    """将同一条信息同时输出到控制台和 UTF-8 日志文件。"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"[{timestamp}] {message}"
    print(formatted_message, flush=True)
    log_file.write(formatted_message + "\n")
    log_file.flush()


def read_tsv_rows(txt_path: Path) -> tuple[list[str], list[list[str]]]:
    """读取制表符分隔的 TXT，并检查每一行的字段数量。"""
    with txt_path.open("r", encoding="utf-8-sig", newline="") as file:
        raw_lines = file.read().splitlines()
    if not raw_lines:
        raise ValueError("TXT 文件为空。")

    header = raw_lines[0].split("\t")
    rows: list[list[str]] = []
    for line_number, line in enumerate(raw_lines[1:], start=2):
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) != len(header):
            raise ValueError(
                f"第 {line_number} 行共有 {len(fields)} 列，表头共有 {len(header)} 列。"
            )
        rows.append(fields)
    return header, rows


def select_upload_data(
    source_header: list[str], source_rows: list[list[str]]
) -> tuple[list[str], list[list[str]]]:
    """按照后台上传模板的字段顺序，从源 TXT 中选择需要上传的数据。"""
    field_mapping = {
        "姓名": "姓名*",
        "职务": "职务*",
        "依据说明": "依据说明",
        "依据链接": "依据链接",
        "排序": "排序*",
        "所属省": "所属省*",
        "所属市": "所属市",
    }
    template_header = list(field_mapping)
    duplicate_fields = {
        field for field in source_header if source_header.count(field) > 1
    }
    if duplicate_fields:
        raise ValueError(f"TXT 表头存在重复字段：{sorted(duplicate_fields)}")

    missing_fields = [
        source_field
        for source_field in field_mapping.values()
        if source_field not in source_header
    ]
    if missing_fields:
        raise ValueError(f"TXT 缺少必需字段：{missing_fields}")

    source_indexes = [source_header.index(field_mapping[field]) for field in template_header]
    selected_rows = [
        [source_row[index].strip() for index in source_indexes]
        for source_row in source_rows
    ]
    return template_header, selected_rows


def generate_excel_bytes(
    expected_header: list[str],
    upload_rows: list[list[str]],
) -> bytes:
    """直接在内存中创建后台导入所需的七列 Excel。"""
    workbook = Workbook()
    try:
        worksheet = workbook.active
        worksheet.title = "官员信息"
        worksheet.append(expected_header)
        for row in upload_rows:
            worksheet.append([None if value == "" else value for value in row])

        output = BytesIO()
        workbook.save(output)
        return output.getvalue()
    finally:
        workbook.close()


def load_token(token_file: Path) -> str:
    """从项目受保护目录读取持久令牌。"""
    if token_file.is_file():
        return token_file.read_text(encoding="utf-8-sig").strip()
    return ""


def save_token(token_file: Path, token: str) -> None:
    """保存新令牌，供后续运行直接复用。"""
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(token, encoding="utf-8", newline="")


def acquire_browser_token(
    chrome_exe: Path,
    user_data_dir: Path,
    cdp_port: int,
    target_url: str,
    page_filter: str,
    rejected_token: str,
    cdp_start_timeout_seconds: int,
    login_wait_seconds: int,
    token_file: Path,
    log_file: TextIO,
) -> str:
    """用 Playwright 管理专用 Chrome，等待用户登录并保存新令牌。"""
    if not chrome_exe.is_file():
        raise FileNotFoundError(f"未找到 Chrome：{chrome_exe}")
    user_data_dir.mkdir(parents=True, exist_ok=True)
    # Playwright 的 Node 驱动会在系统临时目录创建 artifacts。当前运行环境
    # 可能无权写入该目录，因此让专用浏览器进程使用项目内可写的临时目录。
    playwright_temp_dir = user_data_dir / "playwright-temp"
    playwright_temp_dir.mkdir(parents=True, exist_ok=True)
    write_log(
        "正在通过 Playwright 启动专用 Chrome："
        f"调试端口 127.0.0.1:{cdp_port}；用户目录 {user_data_dir}",
        log_file,
    )
    launch_timeout_ms = max(cdp_start_timeout_seconds, 1) * 1000
    deadline = time.monotonic() + login_wait_seconds
    last_page_error: Exception | None = None

    temporary_environment = {
        name: str(playwright_temp_dir) for name in ("TMPDIR", "TMP", "TEMP")
    }
    with patch.dict(os.environ, temporary_environment):
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                str(user_data_dir),
                executable_path=str(chrome_exe),
                headless=False,
                args=[
                    "--remote-debugging-address=127.0.0.1",
                    f"--remote-debugging-port={cdp_port}",
                ],
                timeout=launch_timeout_ms,
            )
            try:
                page = next(
                    (
                        existing_page
                        for existing_page in context.pages
                        if page_filter in existing_page.url
                    ),
                    None,
                )
                if page is None:
                    page = context.new_page()
                page.goto(
                    target_url,
                    wait_until="domcontentloaded",
                    timeout=launch_timeout_ms,
                )
                write_log(
                    "请在已打开的 Chrome 页面中完成登录，脚本将自动继续。",
                    log_file,
                )

                while time.monotonic() < deadline:
                    for existing_page in context.pages:
                        if page_filter not in existing_page.url:
                            continue
                        try:
                            token = str(
                                existing_page.evaluate(
                                    "localStorage.getItem('downed-officials-token') || ''"
                                )
                                or ""
                            ).strip()
                        except Exception as error:
                            last_page_error = error
                            continue
                        if token and token != rejected_token:
                            save_token(token_file, token)
                            write_log("已取得并保存新令牌。", log_file)
                            return token
                    time.sleep(1)
            finally:
                context.close()

    if last_page_error is not None:
        raise TimeoutError(f"等待登录超时；最后一次读取错误：{last_page_error}")
    raise TimeoutError("等待登录超时，未读取到新令牌。")


def parse_response_message(response: requests.Response) -> str:
    """提取不包含鉴权信息的后台错误说明。"""
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()[:500] or f"HTTP {response.status_code}"
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
    return str(payload)[:500]


def upload_excel(
    session: requests.Session,
    upload_url: str,
    token: str,
    filename: str,
    excel_bytes: bytes,
    timeout_seconds: int,
) -> dict:
    """把内存中的 Excel 上传到后台，并返回后台 JSON 结果。"""
    response = session.post(
        upload_url,
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                filename,
                excel_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        timeout=timeout_seconds,
    )
    if not response.ok:
        raise requests.HTTPError(
            f"HTTP {response.status_code}：{parse_response_message(response)}",
            response=response,
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("后台返回的上传结果不是 JSON 对象。")
    return payload


def is_unauthorized(error: Exception) -> bool:
    """判断请求异常是否为 HTTP 401。"""
    return (
        isinstance(error, requests.HTTPError)
        and error.response is not None
        and error.response.status_code == 401
    )


def summarize_upload_result(result: dict) -> str:
    """将后台的上传统计转换为简洁日志文字。"""
    imported = result.get("imported", 0)
    skipped = result.get("skipped", 0)
    errors = result.get("errors")
    error_count = len(errors) if isinstance(errors, list) else 0
    return f"导入 {imported} 条，跳过重复 {skipped} 条，校验失败 {error_count} 条"


def main(
    input_path: str | Path,
    log_path: str | Path,
    base_url: str,
    token_file: str | Path,
    chrome_exe: Path | None,
    chrome_user_data_dir: str | Path,
    cdp_port: int,
    browser_target_url: str,
    browser_page_filter: str,
    cdp_start_timeout_seconds: int,
    login_wait_seconds: int,
    upload_timeout_seconds: int,
    use_environment_proxy: bool,
) -> int:
    """读取根目录规范化结果，在内存中生成 Excel 并上传后台。"""
    input_path = resolve_path_argument(input_path, anchor=__file__)
    log_path = resolve_path_argument(log_path, anchor=__file__)
    log_path = timestamped_output_path(log_path)
    token_file = resolve_path_argument(token_file, anchor=__file__)
    chrome_exe = chrome_exe or find_chrome_executable()
    chrome_user_data_dir = resolve_path_argument(chrome_user_data_dir, anchor=__file__)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with log_path.open("w", encoding="utf-8") as log_file:
        write_log("开始上传官员信息。", log_file)
        if not input_path.is_file():
            write_log(f"错误：输入文件不存在：{input_path}", log_file)
            return 1
        try:
            source_header, source_rows = read_tsv_rows(input_path)
            if source_header != EXPECTED_SOURCE_HEADER:
                raise ValueError(
                    f"输入文件表头不符合十二列契约。实际：{source_header}；"
                    f"预期：{EXPECTED_SOURCE_HEADER}"
                )
            expected_header, upload_rows = select_upload_data(
                source_header, source_rows
            )
            excel_bytes = generate_excel_bytes(expected_header, upload_rows)
            filename = f"{input_path.stem}-官员上传.xlsx"
            token = load_token(token_file)
            upload_url = f"{base_url.rstrip('/')}/api/v1/official-updates/import"

            with requests.Session() as session:
                session.trust_env = use_environment_proxy
                if not token:
                    write_log("本地没有令牌，正在等待网页登录。", log_file)
                    token = acquire_browser_token(
                        chrome_exe,
                        chrome_user_data_dir,
                        cdp_port,
                        browser_target_url,
                        browser_page_filter,
                        "",
                        cdp_start_timeout_seconds,
                        login_wait_seconds,
                        token_file,
                        log_file,
                    )
                try:
                    result = upload_excel(
                        session,
                        upload_url,
                        token,
                        filename,
                        excel_bytes,
                        upload_timeout_seconds,
                    )
                except Exception as error:
                    if not is_unauthorized(error):
                        raise
                    write_log("登录令牌已失效，正在等待网页登录。", log_file)
                    token = acquire_browser_token(
                        chrome_exe,
                        chrome_user_data_dir,
                        cdp_port,
                        browser_target_url,
                        browser_page_filter,
                        token,
                        cdp_start_timeout_seconds,
                        login_wait_seconds,
                        token_file,
                        log_file,
                    )
                    result = upload_excel(
                        session,
                        upload_url,
                        token,
                        filename,
                        excel_bytes,
                        upload_timeout_seconds,
                    )

            write_log(
                f"上传完成：{input_path.name}；{summarize_upload_result(result)}。",
                log_file,
            )
            errors = result.get("errors")
            if isinstance(errors, list):
                for validation_error in errors:
                    write_log(f"校验失败明细：{validation_error}", log_file)
            return 0
        except Exception as error:
            write_log(f"上传失败：{input_path}；原因：{error}", log_file)
            return 1


if __name__ == "__main__":
    input_path_value = r"职务规范4：扩充.txt"
    log_path_value = r"workspace/log/职务比对/上传官员信息.log"
    base_url_value = "http://118.186.244.220:5173"
    token_file_value = r".secrets/official_update_token"
    chrome_exe_value = None
    chrome_user_data_dir_value = r".official_update_chrome_profile"
    cdp_port_value = 9777
    browser_target_url_value = "http://118.186.244.220:5173/official-information"
    browser_page_filter_value = "118.186.244.220"
    cdp_start_timeout_seconds_value = 30
    login_wait_seconds_value = 300
    upload_timeout_seconds_value = 120
    use_environment_proxy_value = False
    sys.exit(
        main(
            input_path_value,
            log_path_value,
            base_url_value,
            token_file_value,
            chrome_exe_value,
            chrome_user_data_dir_value,
            cdp_port_value,
            browser_target_url_value,
            browser_page_filter_value,
            cdp_start_timeout_seconds_value,
            login_wait_seconds_value,
            upload_timeout_seconds_value,
            use_environment_proxy_value,
        )
    )
