from __future__ import annotations

import json
import subprocess
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import TextIO
from urllib.parse import quote

import requests
import websocket
from openpyxl import Workbook

from crawler_core.paths import find_chrome_executable, resolve_path_argument


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


def create_direct_session() -> requests.Session:
    """创建不读取系统代理环境变量的 HTTP 会话。"""
    session = requests.Session()
    session.trust_env = False
    return session


def is_cdp_available(cdp_port: int) -> bool:
    """检查专用 Chrome 的调试端口是否可用。"""
    try:
        with create_direct_session() as session:
            response = session.get(
                f"http://127.0.0.1:{cdp_port}/json/version", timeout=3
            )
            response.raise_for_status()
        return True
    except requests.RequestException:
        return False


def start_debug_chrome(
    chrome_exe: Path,
    user_data_dir: Path,
    cdp_port: int,
    target_url: str,
) -> None:
    """启动专用 Chrome，由用户在可见页面中亲自登录。"""
    if not chrome_exe.is_file():
        raise FileNotFoundError(f"未找到 Chrome：{chrome_exe}")
    user_data_dir.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [
            str(chrome_exe),
            f"--remote-debugging-port={cdp_port}",
            f"--user-data-dir={user_data_dir}",
            "--restore-last-session",
            "--no-first-run",
            "--no-default-browser-check",
            target_url,
        ],
        close_fds=True,
    )


def wait_for_cdp(cdp_port: int, timeout_seconds: int) -> None:
    """等待 Chrome 调试端口启动完成。"""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if is_cdp_available(cdp_port):
            return
        time.sleep(0.5)
    raise TimeoutError(f"Chrome 调试端口启动超时：127.0.0.1:{cdp_port}")


def get_target_page(cdp_port: int, page_filter: str, target_url: str) -> dict:
    """查找后台页面；不存在时通过 CDP 新建标签页。"""
    endpoint = f"http://127.0.0.1:{cdp_port}"
    with create_direct_session() as session:
        pages = session.get(f"{endpoint}/json", timeout=5).json()
        for page in pages:
            if page.get("type") == "page" and page_filter in str(page.get("url") or ""):
                return page
        encoded_url = quote(target_url, safe="")
        response = session.put(f"{endpoint}/json/new?{encoded_url}", timeout=10)
        response.raise_for_status()
        page = response.json()
    if not isinstance(page, dict):
        raise ValueError("Chrome 调试接口没有返回有效页面对象。")
    return page


def read_page_token(page: dict) -> str:
    """从后台页面的 localStorage 读取登录令牌。"""
    websocket_url = str(page.get("webSocketDebuggerUrl") or "")
    if not websocket_url:
        return ""
    connection = websocket.create_connection(websocket_url, timeout=10, suppress_origin=True)
    try:
        message_id = 1
        connection.send(
            json.dumps(
                {
                    "id": message_id,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": (
                            "localStorage.getItem('downed-officials-token') || ''"
                        ),
                        "returnByValue": True,
                    },
                },
                ensure_ascii=False,
            )
        )
        while True:
            response = json.loads(connection.recv())
            if response.get("id") == message_id:
                return str(
                    response.get("result", {}).get("result", {}).get("value") or ""
                ).strip()
    finally:
        connection.close()


def navigate_page(page: dict, target_url: str) -> None:
    """进入上传页面，以触发失效令牌的登录跳转。"""
    websocket_url = str(page.get("webSocketDebuggerUrl") or "")
    if not websocket_url:
        raise ValueError("Chrome 页面缺少 webSocketDebuggerUrl。")
    connection = websocket.create_connection(websocket_url, timeout=10, suppress_origin=True)
    try:
        message_id = 2
        connection.send(
            json.dumps(
                {
                    "id": message_id,
                    "method": "Page.navigate",
                    "params": {"url": target_url},
                },
                ensure_ascii=False,
            )
        )
        while True:
            response = json.loads(connection.recv())
            if response.get("id") == message_id:
                return
    finally:
        connection.close()


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
    """等待用户登录，从 Chrome 获取并保存不同于失效值的新令牌。"""
    if not is_cdp_available(cdp_port):
        start_debug_chrome(chrome_exe, user_data_dir, cdp_port, target_url)
        wait_for_cdp(cdp_port, cdp_start_timeout_seconds)

    page = get_target_page(cdp_port, page_filter, target_url)
    navigate_page(page, target_url)
    write_log("请在已打开的 Chrome 页面中完成登录，脚本将自动继续。", log_file)

    deadline = time.monotonic() + login_wait_seconds
    last_page_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            page = get_target_page(cdp_port, page_filter, target_url)
            token = read_page_token(page)
            if token and token != rejected_token:
                save_token(token_file, token)
                write_log("已取得并保存新令牌。", log_file)
                return token
        except Exception as error:
            last_page_error = error
        time.sleep(1)

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
    input_path_value = r"important_people/职务规范4：扩充.txt"
    log_path_value = r"important_people/workspace/log/职务比对/上传官员信息.log"
    base_url_value = "http://118.186.244.220:5173"
    token_file_value = r"important_people/.secrets/official_update_token"
    chrome_exe_value = None
    chrome_user_data_dir_value = r"important_people/.official_update_chrome_profile"
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
