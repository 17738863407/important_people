"""启动仅供本机访问的机构数据工作台 HTTP 服务。"""

from __future__ import annotations

import json
import logging
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from crawler_core.paths import resolve_project_path

from .storage import WorkbenchStore


def configure_logging(log_path: Path) -> logging.Logger:
    """配置同时写入控制台和 UTF-8 日志文件的日志器。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("institution_workbench")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8", mode="a")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def build_handler(
    store: WorkbenchStore,
    static_dir: Path,
    logger: logging.Logger,
) -> type[BaseHTTPRequestHandler]:
    """创建绑定工作库和静态目录的请求处理器。"""

    class WorkbenchHandler(BaseHTTPRequestHandler):
        server_version = "InstitutionWorkbench/1.0"

        def log_message(self, format_text: str, *args: object) -> None:
            logger.info("%s - %s", self.address_string(), format_text % args)

        def send_security_headers(self) -> None:
            """发送本地应用仍应具备的基础安全响应头。"""
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'",
            )

        def send_json(self, payload: object, status: int = HTTPStatus.OK) -> None:
            """发送 UTF-8 JSON 响应。"""
            content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_security_headers()
            self.end_headers()
            self.wfile.write(content)

        def read_json(self) -> dict[str, object]:
            """读取并校验 JSON 请求体。"""
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length > 5 * 1024 * 1024:
                raise ValueError("请求内容过大")
            raw = self.rfile.read(content_length)
            if not raw:
                return {}
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("请求体必须是 JSON 对象")
            return payload

        def serve_static(self, relative_path: str) -> None:
            """只允许读取预先指定的本地静态文件。"""
            allowed_files = {
                "": "index.html",
                "/": "index.html",
                "/index.html": "index.html",
                "/app.js": "app.js",
                "/styles.css": "styles.css",
                "/icons.svg": "icons.svg",
            }
            filename = allowed_files.get(relative_path)
            if filename is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            path = static_dir / filename
            if not path.exists():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content = path.read_bytes()
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if path.suffix in {".html", ".js", ".css", ".svg"}:
                content_type += "; charset=utf-8"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_security_headers()
            self.end_headers()
            self.wfile.write(content)

        def handle_error(self, exc: Exception) -> None:
            """把可预期错误转换为结构化响应。"""
            logger.exception("请求处理失败：%s %s", self.command, self.path)
            if isinstance(exc, KeyError):
                status = HTTPStatus.NOT_FOUND
            elif isinstance(exc, RuntimeError):
                status = HTTPStatus.CONFLICT
            elif isinstance(exc, (ValueError, json.JSONDecodeError)):
                status = HTTPStatus.BAD_REQUEST
            else:
                status = HTTPStatus.INTERNAL_SERVER_ERROR
            message = str(exc).strip("'") or "服务器处理失败"
            self.send_json({"error": message}, status)

        def do_GET(self) -> None:
            """处理页面、状态、历史和正式文件下载。"""
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/state":
                    self.send_json(store.state())
                elif parsed.path == "/api/history":
                    limit = int(parse_qs(parsed.query).get("limit", ["200"])[0])
                    self.send_json({"history": store.history(limit)})
                elif parsed.path == "/api/download":
                    content = store.source_path.read_bytes()
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Disposition", "attachment; filename*=UTF-8''institution-full-table.txt")
                    self.send_header("Content-Length", str(len(content)))
                    self.send_security_headers()
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    self.serve_static(parsed.path)
            except Exception as exc:
                self.handle_error(exc)

        def do_POST(self) -> None:
            """处理新增、复制、删除、批量修改、发布、同步和撤销。"""
            parsed = urlparse(self.path)
            try:
                payload = self.read_json()
                path_parts = [part for part in parsed.path.split("/") if part]
                if parsed.path == "/api/records":
                    self.send_json(store.create_record(payload.get("values") if isinstance(payload.get("values"), dict) else None), HTTPStatus.CREATED)
                elif len(path_parts) == 4 and path_parts[:2] == ["api", "records"] and path_parts[3] == "duplicate":
                    self.send_json(store.create_record(duplicate_from=path_parts[2]), HTTPStatus.CREATED)
                elif len(path_parts) == 4 and path_parts[:2] == ["api", "records"] and path_parts[3] in {"delete", "restore"}:
                    self.send_json(store.set_deleted(path_parts[2], path_parts[3] == "delete"))
                elif parsed.path == "/api/bulk":
                    record_ids = payload.get("record_ids", [])
                    if not isinstance(record_ids, list):
                        raise ValueError("record_ids 必须是数组")
                    self.send_json(store.bulk_update([str(value) for value in record_ids], str(payload.get("field_id", "")), payload.get("value", "")))
                elif parsed.path == "/api/publish":
                    self.send_json(store.publish())
                elif parsed.path == "/api/reconcile":
                    self.send_json(store.reconcile())
                elif parsed.path == "/api/undo":
                    self.send_json(store.undo())
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)
            except Exception as exc:
                self.handle_error(exc)

        def do_PATCH(self) -> None:
            """处理单元格修改和字段真实改名。"""
            parsed = urlparse(self.path)
            try:
                payload = self.read_json()
                path_parts = [part for part in parsed.path.split("/") if part]
                if len(path_parts) == 3 and path_parts[:2] == ["api", "records"]:
                    self.send_json(store.update_record(path_parts[2], str(payload.get("field_id", "")), payload.get("value", "")))
                elif len(path_parts) == 3 and path_parts[:2] == ["api", "fields"]:
                    self.send_json(store.rename_field(path_parts[2], payload.get("export_name", "")))
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)
            except Exception as exc:
                self.handle_error(exc)

    return WorkbenchHandler


def main(
    host: str,
    port: int,
    source_path: Path,
    database_path: Path,
    backup_dir: Path,
    static_dir: Path,
    log_path: Path,
) -> None:
    """初始化工作库并持续运行本地 HTTP 服务。"""
    logger = configure_logging(log_path)
    store = WorkbenchStore(database_path, source_path, backup_dir)
    handler = build_handler(store, static_dir, logger)
    server = ThreadingHTTPServer((host, port), handler)
    logger.info("机构数据工作台已启动：http://%s:%d", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("机构数据工作台已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    server_host = "127.0.0.1"
    server_port = 8765
    input_source_path = resolve_project_path(
        r"important_people/workspace/source_data/机构主表.txt", anchor=__file__, must_exist=True
    )
    output_database_path = resolve_project_path(
        r"important_people/workspace/institution_catalog/workbench/data/institution_workbench.db",
        anchor=__file__,
    )
    output_backup_dir = resolve_project_path(
        r"important_people/workspace/source_data/backup/机构主表/web_edits", anchor=__file__
    )
    input_static_dir = resolve_project_path(
        r"important_people/workspace/institution_catalog/workbench/static",
        anchor=__file__,
        must_exist=True,
    )
    output_log_path = resolve_project_path(
        r"important_people/workspace/log/机构数据工作台.log", anchor=__file__
    )
    main(
        server_host,
        server_port,
        input_source_path,
        output_database_path,
        output_backup_dir,
        input_static_dir,
        output_log_path,
    )
