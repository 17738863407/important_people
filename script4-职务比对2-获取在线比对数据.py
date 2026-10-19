# -*- coding: utf-8 -*-
"""提取内容安全审校系统“官员更新提醒”全量数据。

数据接口：
    GET /api/v1/official-updates/reminders?page=<页码>&page_size=<每页条数>
    请求头：Authorization: Bearer <token>

登录与令牌：
    从项目目录下的 .secrets/official_update_token 文件读取令牌。令牌缺失或失效时，
    自动启动专用 Chrome、
    打开系统页面并等待用户完成登录，然后从页面 localStorage 中提取新令牌，保存后
    继续抓取。脚本不读取、不保存账号和密码，令牌也不写入日志或数据输出。

输出：
    固定写入项目根目录下的“职务比对2：在线比对数据.txt”，采用 UTF-8 编码和
    制表符分隔。
"""

from __future__ import annotations

import json
import logging
import math
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests
import websocket

from crawler_core.paths import find_chrome_executable, resolve_path_argument


SPLIT_HEADERS = [
    "姓名",
    "本地职务",
    "职级",
    "排序",
    "所属省",
    "所属市",
    "提醒类型",
    "老数据职务",
    "依据链接",
    "需要更新时间",
    "操作",
]


def setup_logging(log_path: Path) -> None:
    """配置日志，同时输出到控制台与日志文件。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )


def clean_cell(value: object) -> str:
    """清理单元格中的制表符与换行，避免破坏 TSV 结构。"""
    if value is None:
        return ""
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def join_remote_titles(remote_titles: list | None) -> str:
    """把多条老数据职务合并为一行，使用斜杠分隔。"""
    if not remote_titles:
        return ""
    return clean_cell("/".join(str(title) for title in remote_titles))


def format_datetime(value: str | None) -> str:
    """把接口时间格式转换为空格分隔的日期时间。"""
    if not value:
        return ""
    return str(value).replace("T", " ")[:19]


def map_reminder_type(value: str | None) -> str:
    """把接口提醒类型转换为中文。"""
    if value == "missing":
        return "需要新增"
    if value == "changed":
        return "职务变更"
    return clean_cell(value)


def load_token(token_file: Path) -> str:
    """从项目受保护目录读取持久令牌。"""
    if token_file.is_file():
        return token_file.read_text(encoding="utf-8-sig").strip()
    return ""


def create_direct_session() -> requests.Session:
    """创建不读取系统代理环境变量的 HTTP 会话。"""
    session = requests.Session()
    session.trust_env = False
    return session


def is_cdp_available(cdp_port: int) -> bool:
    """检查本机 Chrome DevTools 调试端口是否可用。"""
    try:
        with create_direct_session() as session:
            response = session.get(f"http://127.0.0.1:{cdp_port}/json/version", timeout=3)
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
    """启动带远程调试端口的专用 Chrome，供用户在可见页面中登录。"""
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
    """查找系统页面；不存在时通过 CDP 新建标签页。"""
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
        raise ValueError("Chrome 调试接口没有返回有效页面对象")
    return page


def read_page_token(page: dict) -> str:
    """通过 Chrome DevTools Protocol 读取系统页面保存的令牌。"""
    websocket_url = str(page.get("webSocketDebuggerUrl") or "")
    if not websocket_url:
        return ""
    connection = websocket.create_connection(websocket_url, timeout=10, suppress_origin=True)
    try:
        message_id = 1
        request = {
            "id": message_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": "localStorage.getItem('downed-officials-token') || ''",
                "returnByValue": True,
            },
        }
        connection.send(json.dumps(request, ensure_ascii=False))
        while True:
            response = json.loads(connection.recv())
            if response.get("id") != message_id:
                continue
            return str(
                response.get("result", {}).get("result", {}).get("value") or ""
            ).strip()
    finally:
        connection.close()


def navigate_page(page: dict, target_url: str) -> None:
    """让目标标签页重新进入系统页面，以触发失效令牌的登录跳转。"""
    websocket_url = str(page.get("webSocketDebuggerUrl") or "")
    if not websocket_url:
        raise ValueError("Chrome 页面缺少 webSocketDebuggerUrl")
    connection = websocket.create_connection(websocket_url, timeout=10, suppress_origin=True)
    try:
        message_id = 2
        request = {
            "id": message_id,
            "method": "Page.navigate",
            "params": {"url": target_url},
        }
        connection.send(json.dumps(request, ensure_ascii=False))
        while True:
            response = json.loads(connection.recv())
            if response.get("id") == message_id:
                return
    finally:
        connection.close()


def wait_for_browser_token(
    chrome_exe: Path,
    user_data_dir: Path,
    cdp_port: int,
    target_url: str,
    page_filter: str,
    rejected_token: str,
    cdp_start_timeout_seconds: int,
    login_wait_seconds: int,
) -> str:
    """打开系统页面，并等待浏览器产生不同于失效值的新令牌。"""
    if not is_cdp_available(cdp_port):
        start_debug_chrome(chrome_exe, user_data_dir, cdp_port, target_url)
        wait_for_cdp(cdp_port, cdp_start_timeout_seconds)

    page = get_target_page(cdp_port, page_filter, target_url)
    navigate_page(page, target_url)
    logging.info("请在已打开的 Chrome 页面中完成登录，脚本将自动继续")
    deadline = time.monotonic() + login_wait_seconds
    last_page_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            page = get_target_page(cdp_port, page_filter, target_url)
            token = read_page_token(page)
            if token and token != rejected_token:
                return token
        except Exception as error:
            last_page_error = error
        time.sleep(1)

    if last_page_error is not None:
        raise TimeoutError(f"等待浏览器登录超时；最后一次读取错误：{last_page_error}")
    raise TimeoutError("等待浏览器登录超时，未读取到新令牌")


def save_token(token_file: Path, token: str) -> None:
    """把新令牌持久保存到本地文件，供下次运行直接使用。"""
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(token, encoding="utf-8", newline="")


def is_unauthorized(error: Exception) -> bool:
    """判断 requests 异常是否为 HTTP 401。"""
    return (
        isinstance(error, requests.HTTPError)
        and error.response is not None
        and error.response.status_code == 401
    )


def fetch_page(
    session: requests.Session,
    base_url: str,
    token: str,
    page: int,
    page_size: int,
) -> dict:
    """获取单页数据，失败时抛出异常由调用方重试。"""
    url = f"{base_url}/api/v1/official-updates/reminders"
    params = {"page": page, "page_size": page_size}
    headers = {"Authorization": f"Bearer {token}"}
    response = session.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"接口第 {page} 页返回的 JSON 不是对象")
    return payload


def fetch_page_with_retry(
    session: requests.Session,
    base_url: str,
    token: str,
    page: int,
    page_size: int,
    max_retries: int,
) -> dict:
    """抓取指定页并重试，全部失败后抛出最后一次异常。"""
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return fetch_page(session, base_url, token, page, page_size)
        except Exception as error:
            last_error = error
            if is_unauthorized(error):
                raise
            if attempt < max_retries:
                logging.warning(
                    "第 %d 页第 %d/%d 次抓取失败：%s；稍后重试",
                    page,
                    attempt,
                    max_retries,
                    error,
                )
                time.sleep(float(attempt))
    assert last_error is not None
    raise last_error


def fetch_all(
    session: requests.Session,
    base_url: str,
    token: str,
    page_size: int,
    max_retries: int,
) -> tuple[list[dict], int, list[int]]:
    """按分页抓取全部数据，返回记录、总数和失败页码。"""
    first = fetch_page_with_retry(session, base_url, token, 1, page_size, max_retries)
    total = int(first.get("total") or 0)
    total_pages = max(1, math.ceil(total / page_size)) if total else 1
    first_items = first.get("items") or []
    if not isinstance(first_items, list):
        raise ValueError("接口第一页的 items 字段不是数组")
    all_items: list[dict] = list(first_items)
    failed_pages: list[int] = []

    try:
        from tqdm import tqdm
    except Exception:
        tqdm = None

    iterator = range(2, total_pages + 1)
    if tqdm is not None:
        iterator = tqdm(iterator, desc="抓取更新提醒分页", unit="页")
    for page in iterator:
        try:
            payload = fetch_page_with_retry(
                session,
                base_url,
                token,
                page,
                page_size,
                max_retries,
            )
            items = payload.get("items") or []
            if not isinstance(items, list):
                raise ValueError(f"接口第 {page} 页的 items 字段不是数组")
            all_items.extend(items)
        except Exception as error:
            failed_pages.append(page)
            logging.error(
                "第 %d 页抓取失败（重试 %d 次后放弃）：%s",
                page,
                max_retries,
                error,
            )
    return all_items, total, failed_pages


def write_tsv(items: list[dict], output_path: Path) -> None:
    """按网页表头顺序写出 TSV。"""
    with open(output_path, "w", encoding="utf-8", newline="\n") as file_handle:
        file_handle.write("\t".join(SPLIT_HEADERS) + "\n")
        for item in items:
            row = [
                clean_cell(item.get("name")),
                clean_cell(item.get("title")),
                clean_cell(item.get("level")),
                clean_cell(item.get("leader_order")),
                clean_cell(item.get("province")),
                clean_cell(item.get("city")),
                map_reminder_type(item.get("reminder_type")),
                join_remote_titles(item.get("remote_titles")),
                clean_cell(item.get("according_link")),
                format_datetime(item.get("needs_update_at")),
                "删除",
            ]
            file_handle.write("\t".join(row) + "\n")


def acquire_browser_token(
    chrome_exe: Path,
    chrome_user_data_dir: Path,
    cdp_port: int,
    browser_target_url: str,
    browser_page_filter: str,
    rejected_token: str,
    cdp_start_timeout_seconds: int,
    login_wait_seconds: int,
    token_file: Path,
) -> str:
    """从 Chrome 获取并保存新令牌。"""
    token = wait_for_browser_token(
        chrome_exe,
        chrome_user_data_dir,
        cdp_port,
        browser_target_url,
        browser_page_filter,
        rejected_token,
        cdp_start_timeout_seconds,
        login_wait_seconds,
    )
    save_token(token_file, token)
    logging.info("已从 Chrome 获取新令牌并保存")
    return token


def main(
    base_url: str,
    page_size: int,
    max_retries: int,
    output_path: str | Path,
    log_dir: str | Path,
    token_file: str | Path,
    chrome_exe: Path | None,
    chrome_user_data_dir: str | Path,
    cdp_port: int,
    browser_target_url: str,
    browser_page_filter: str,
    cdp_start_timeout_seconds: int,
    login_wait_seconds: int,
    use_environment_proxy: bool,
) -> None:
    """统一入口：获取有效令牌，抓取全量提醒并写出 TSV。"""
    output_path = resolve_path_argument(output_path, anchor=__file__)
    log_dir = resolve_path_argument(log_dir, anchor=__file__)
    token_file = resolve_path_argument(token_file, anchor=__file__)
    chrome_exe = chrome_exe or find_chrome_executable()
    chrome_user_data_dir = resolve_path_argument(chrome_user_data_dir, anchor=__file__)
    date_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"fetch_official_update_reminders_{date_tag}.log"
    setup_logging(log_path)
    token = load_token(token_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_base_url = base_url.rstrip("/")
    logging.info(
        "开始抓取：接口 %s，每页 %d 条",
        f"{normalized_base_url}/api/v1/official-updates/reminders",
        page_size,
    )

    with requests.Session() as session:
        session.trust_env = use_environment_proxy
        if not token:
            logging.info("本地没有可用令牌，正在从 Chrome 登录状态获取")
            try:
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
                )
            except Exception as error:
                logging.error("%s", error)
                raise SystemExit(1) from error

        try:
            items, total, failed_pages = fetch_all(
                session,
                normalized_base_url,
                token,
                page_size,
                max_retries,
            )
        except Exception as error:
            if not is_unauthorized(error):
                raise
            logging.warning("登录令牌已失效，正在等待 Chrome 获取新令牌")
            try:
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
                )
            except Exception as browser_error:
                logging.error("%s", browser_error)
                raise SystemExit(1) from browser_error
            logging.info("正在使用新令牌重新抓取")
            items, total, failed_pages = fetch_all(
                session,
                normalized_base_url,
                token,
                page_size,
                max_retries,
            )

    if failed_pages:
        raise RuntimeError(
            f"在线比对数据抓取不完整，失败页码：{failed_pages}；未覆盖旧结果"
        )
    if len(items) != total:
        raise RuntimeError(
            f"在线比对数据数量不完整：接口声明 {total} 条，实际取得 {len(items)} 条；"
            "未覆盖旧结果"
        )
    logging.info("接口声明总数 %d，实际抓取 %d 条", total, len(items))
    write_tsv(items, output_path)
    logging.info("TXT 已写出：%s（%d 行数据）", output_path, len(items))
    print(f"输出文件：{output_path}")
    print(f"总记录数：{len(items)} / {total}，失败页码：{failed_pages or '无'}")


if __name__ == "__main__":
    base_url_value = "http://118.186.244.220:5173"
    page_size_value = 20
    max_retries_value = 3
    output_path_value = r"important_people/职务比对2：在线比对数据.txt"
    log_dir_value = r"important_people/workspace/log/职务比对"
    token_file_value = r"important_people/.secrets/official_update_token"
    chrome_exe_value = None
    chrome_user_data_dir_value = r"important_people/.official_update_chrome_profile"
    cdp_port_value = 9777
    browser_target_url_value = "http://118.186.244.220:5173/official-update-reminders"
    browser_page_filter_value = "118.186.244.220"
    cdp_start_timeout_seconds_value = 30
    login_wait_seconds_value = 300
    use_environment_proxy_value = False
    main(
        base_url_value,
        page_size_value,
        max_retries_value,
        output_path_value,
        log_dir_value,
        token_file_value,
        chrome_exe_value,
        chrome_user_data_dir_value,
        cdp_port_value,
        browser_target_url_value,
        browser_page_filter_value,
        cdp_start_timeout_seconds_value,
        login_wait_seconds_value,
        use_environment_proxy_value,
    )
