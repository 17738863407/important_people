from __future__ import annotations

import os
from pathlib import Path
import runpy
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import requests

from crawler_core.fetch_memory import (
    FetchMemoryRecord,
    fetch_memory_lock_path,
    load_fetch_memory,
    migrate_fetch_memory,
    normalize_actual_collector,
    preferred_fetch_mode,
    record_fetch_success,
)
from crawler_core.fetcher import (
    DomainCircuitOpenError,
    FetchResult,
    build_requests_timeout,
    disable_unavailable_loopback_proxies,
    enforce_fetch_deadline,
    fetch_by_raw_requests,
    fetch_by_playwright,
    fetch_html_with_preferred_fallback,
    is_configured_python,
    open_chrome_page_with_fallback,
    remaining_fetch_timeout,
    requests_get_html,
    resolve_python_executable,
    reset_domain_circuit_breakers,
    reset_chrome_warmup_cache,
    should_retry_playwright_in_subprocess,
    warm_up_chrome_context_once,
)
from crawler_core.detail_links import DetailLink, parse_detail_chain_records
from crawler_core.models import PersonRecord
from crawler_core.runner import fetch_html_for_rule, run_page_adapter
from crawler_core.settings import CrawlerSettings


class FetchMemoryTests(unittest.TestCase):
    """验证四列记忆表的兼容迁移和动态调度映射。"""

    def test_legacy_online_is_not_guessed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            memory_path = root / "module" / "采集方式成功记录.txt"
            memory_path.parent.mkdir(parents=True)
            memory_path.write_text(
                "脚本序号\t脚本名\t机构\t网址\t成功采集方式\t成功轮次\t实际采集链路\t全局采集链路\t递减并发计划\t耗时秒\t最近成功时间\t成功次数\n"
                "0001\t0001_A.py\tA\thttps://a.example\traw_http\t第1轮\t\t\t\t1.0\t20260820_000000\t1\n"
                "0002\t0002_B.py\tB\thttps://b.example\tonline\t第1轮\t\t\t\t2.0\t20260821_000000\t1\n"
                "0003\t0003_C.py\tC\thttps://c.example\tchrome\t第1轮\t\t\t\t3.0\t20260822_000000\t1\n",
                encoding="utf-8",
            )

            records = load_fetch_memory(memory_path)

            self.assertEqual(set(records), {"0001", "0003"})
            self.assertEqual(records["0003"].actual_collector, "chrome_cdp")
            backup_path, migrated_records = migrate_fetch_memory(
                memory_path,
                root / "reports",
                "20260823_000000",
            )
            self.assertIsNotNone(backup_path)
            self.assertEqual(set(migrated_records), {"0001", "0003"})
            self.assertEqual(
                memory_path.read_text(encoding="utf-8").splitlines()[0],
                "脚本序号\t实际成功采集器\t执行形态\t最近成功时间",
            )

    def test_playwright_subprocess_is_execution_mode(self) -> None:
        self.assertEqual(
            normalize_actual_collector("playwright_subprocess"),
            ("playwright", "subprocess"),
        )
        record = FetchMemoryRecord("0001", "playwright", "subprocess", "20260823_000000")
        self.assertEqual(preferred_fetch_mode(record), "playwright")

    def test_record_success_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            memory_path = Path(temporary_dir) / "module" / "采集方式成功记录.txt"
            record_fetch_success(
                memory_path,
                "12",
                "playwright",
                "subprocess",
                "20260823_010203",
            )
            record = load_fetch_memory(memory_path)["0012"]
            self.assertEqual(record.actual_collector, "playwright")
            self.assertEqual(record.execution_mode, "subprocess")
            self.assertNotEqual(fetch_memory_lock_path(memory_path).parent, memory_path.parent)


class PlaywrightStorageTests(unittest.TestCase):
    """验证 Playwright 不再向项目目录写入持久化浏览器画像。"""

    def test_project_does_not_use_persistent_playwright_profiles(self) -> None:
        project_dir = Path(__file__).resolve().parents[2]
        source_paths = [
            project_dir / "crawler_core" / "fetcher.py",
            project_dir / "crawler_core" / "playwright_fetch_helper.py",
        ]
        combined_source = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)

        self.assertNotIn("launch_persistent_context", combined_source)
        self.assertNotIn(".playwright_profiles", combined_source)


class FetcherClassificationTests(unittest.TestCase):
    """验证Playwright子进程只处理运行环境类故障。"""

    def test_python_executable_inherits_current_uv_process_by_default(self) -> None:
        with patch("crawler_core.fetcher.SETTINGS", CrawlerSettings(python_exe="")):
            self.assertEqual(resolve_python_executable(), sys.executable)
            self.assertTrue(is_configured_python())

    def test_explicit_python_executable_remains_supported(self) -> None:
        configured_python = str(Path(sys.executable).resolve())
        with patch(
            "crawler_core.fetcher.SETTINGS",
            CrawlerSettings(python_exe=configured_python),
        ):
            self.assertEqual(resolve_python_executable(), configured_python)
            self.assertTrue(is_configured_python())

    def test_runtime_error_uses_subprocess(self) -> None:
        self.assertTrue(should_retry_playwright_in_subprocess(RuntimeError("Event loop is closed")))

    def test_page_error_skips_subprocess(self) -> None:
        self.assertFalse(
            should_retry_playwright_in_subprocess(RuntimeError("Playwright 渲染结果疑似无效：HTML 长度过短"))
        )

    def test_unavailable_environment_proxy_falls_back_to_direct_session(self) -> None:
        expected_response = requests.Response()
        with (
            patch(
                "crawler_core.fetcher.REQUESTS_SESSION.get",
                side_effect=requests.exceptions.ProxyError("proxy unavailable"),
            ),
            patch(
                "crawler_core.fetcher.DIRECT_REQUESTS_SESSION.get",
                return_value=expected_response,
            ) as direct_get,
        ):
            actual_response = requests_get_html("https://example.com", timeout=10, verify=True)

        self.assertIs(actual_response, expected_response)
        direct_get.assert_called_once()

    def test_unavailable_loopback_proxy_is_removed_only_in_current_process(self) -> None:
        proxy_variables = {
            "HTTP_PROXY": "http://127.0.0.1:7890",
            "HTTPS_PROXY": "http://127.0.0.1:7890",
        }
        with (
            patch.dict(os.environ, proxy_variables, clear=False),
            patch("crawler_core.fetcher.socket.create_connection", side_effect=OSError("拒绝连接")),
        ):
            removed_variables = disable_unavailable_loopback_proxies(timeout=0.01)
            self.assertTrue(set(proxy_variables).issubset(set(removed_variables)))
            self.assertNotIn("HTTP_PROXY", os.environ)
            self.assertNotIn("HTTPS_PROXY", os.environ)

    def test_managed_codex_proxy_is_not_removed_when_socket_probe_is_blocked(self) -> None:
        proxy_variables = {
            "HTTP_PROXY": "http://127.0.0.1:3128",
            "HTTPS_PROXY": "http://127.0.0.1:3128",
            "ALL_PROXY": "socks5h://127.0.0.1:8081",
            "CODEX_NETWORK_PROXY_ACTIVE": "1",
            "CODEX_WINDOWS_SANDBOX_PROXY_PORTS": "3128,8081",
        }
        with (
            patch.dict(os.environ, proxy_variables, clear=False),
            patch("crawler_core.fetcher.socket.create_connection", side_effect=OSError("WinError 10013")),
        ):
            removed_variables = disable_unavailable_loopback_proxies(timeout=0.01)
            self.assertEqual(removed_variables, [])
            self.assertEqual(os.environ["HTTP_PROXY"], proxy_variables["HTTP_PROXY"])
            self.assertEqual(os.environ["HTTPS_PROXY"], proxy_variables["HTTPS_PROXY"])
            self.assertEqual(os.environ["ALL_PROXY"], proxy_variables["ALL_PROXY"])

    def test_malformed_proxy_port_does_not_interrupt_runner(self) -> None:
        with patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:not-a-port"}, clear=True):
            self.assertEqual(disable_unavailable_loopback_proxies(timeout=0.01), [])
            self.assertIn("HTTP_PROXY", os.environ)

    def test_fetch_deadline_limits_later_detail_requests(self) -> None:
        with enforce_fetch_deadline(0.01):
            time.sleep(0.02)
            with self.assertRaisesRegex(TimeoutError, "单脚本总运行超时"):
                remaining_fetch_timeout(30)

    def test_request_timeout_separates_connect_and_read_budget(self) -> None:
        self.assertEqual(build_requests_timeout(30), (8.0, 22.0))

    def test_http_404_stops_retry_immediately(self) -> None:
        response = requests.Response()
        response.status_code = 404
        response.url = "https://example.com/missing"
        reset_domain_circuit_breakers()
        with patch("crawler_core.fetcher.REQUESTS_SESSION.get", return_value=response) as request_get:
            with self.assertRaisesRegex(RuntimeError, "404"):
                fetch_by_raw_requests(response.url, timeout=10, max_retries=3)
        request_get.assert_called_once()

    def test_dns_failure_opens_domain_circuit(self) -> None:
        url = "https://dns-failure.example/page"
        reset_domain_circuit_breakers()
        dns_error = requests.exceptions.ConnectionError(
            "NameResolutionError: getaddrinfo failed"
        )
        with patch("crawler_core.fetcher.REQUESTS_SESSION.get", side_effect=dns_error) as request_get:
            with self.assertRaisesRegex(RuntimeError, "NameResolutionError"):
                fetch_by_raw_requests(url, timeout=10, max_retries=3)
            with self.assertRaisesRegex(DomainCircuitOpenError, "域名熔断"):
                fetch_by_raw_requests(url, timeout=10, max_retries=3)
        request_get.assert_called_once()
        reset_domain_circuit_breakers()

    def test_two_connection_failures_open_domain_circuit(self) -> None:
        url = "https://connection-failure.example/page"
        reset_domain_circuit_breakers()
        connection_error = requests.exceptions.ConnectionError("connection reset")
        with patch("crawler_core.fetcher.REQUESTS_SESSION.get", side_effect=connection_error) as request_get:
            with self.assertRaisesRegex(RuntimeError, "connection reset"):
                fetch_by_raw_requests(url, timeout=10, max_retries=2)
            with self.assertRaisesRegex(DomainCircuitOpenError, "域名熔断"):
                fetch_by_raw_requests(url, timeout=10, max_retries=2)
        self.assertEqual(request_get.call_count, 2)
        reset_domain_circuit_breakers()

    def test_two_read_timeouts_open_domain_circuit(self) -> None:
        url = "https://read-timeout.example/page"
        reset_domain_circuit_breakers()
        read_timeout = requests.exceptions.ReadTimeout("read timed out")
        with patch("crawler_core.fetcher.REQUESTS_SESSION.get", side_effect=read_timeout) as request_get:
            with self.assertRaisesRegex(RuntimeError, "read timed out"):
                fetch_by_raw_requests(url, timeout=10, max_retries=2)
            with self.assertRaisesRegex(DomainCircuitOpenError, "域名熔断"):
                fetch_by_raw_requests(url, timeout=10, max_retries=2)
        self.assertEqual(request_get.call_count, 2)
        reset_domain_circuit_breakers()

    def test_chrome_warmup_runs_once_for_same_context_and_domain(self) -> None:
        reset_chrome_warmup_cache()
        context = object()
        with patch(
            "crawler_core.fetcher.warm_up_browser_context",
            return_value=["已预热"],
        ) as warm_up:
            first_warnings = warm_up_chrome_context_once(
                context,
                "https://example.com/first/detail.html",
                10,
                browser_identity="browser-1",
                context_index=0,
            )
            second_warnings = warm_up_chrome_context_once(
                context,
                "https://example.com/second/detail.html",
                10,
                browser_identity="browser-1",
                context_index=0,
            )

        self.assertEqual(first_warnings, ["已预热"])
        self.assertEqual(second_warnings, [])
        warm_up.assert_called_once()
        reset_chrome_warmup_cache()

    def test_chrome_valid_direct_page_skips_warmup(self) -> None:
        page = object()
        valid_html = "<html><body>" + ("有效正文" * 800) + "</body></html>"
        with (
            patch(
                "crawler_core.fetcher.open_rendered_page",
                return_value=(page, valid_html, "https://example.com/leaders"),
            ) as open_page,
            patch("crawler_core.fetcher.warm_up_chrome_context_once") as warm_up,
        ):
            result = open_chrome_page_with_fallback(
                object(),
                "https://example.com/leaders",
                30,
                3000,
                browser_identity="browser-1",
                context_index=0,
            )

        self.assertIs(result[0], page)
        self.assertEqual(result[1], valid_html)
        self.assertEqual(result[3], [])
        open_page.assert_called_once()
        warm_up.assert_not_called()

    def test_chrome_invalid_direct_page_warms_up_then_retries(self) -> None:
        class FakePage:
            def __init__(self) -> None:
                self.closed = False

            def close(self) -> None:
                self.closed = True

        first_page = FakePage()
        second_page = FakePage()
        valid_html = "<html><body>" + ("有效正文" * 800) + "</body></html>"
        with (
            patch(
                "crawler_core.fetcher.open_rendered_page",
                side_effect=[
                    (first_page, "<html></html>", "https://example.com/leaders"),
                    (second_page, valid_html, "https://example.com/leaders"),
                ],
            ) as open_page,
            patch(
                "crawler_core.fetcher.warm_up_chrome_context_once",
                return_value=["已预热"],
            ) as warm_up,
        ):
            result = open_chrome_page_with_fallback(
                object(),
                "https://example.com/leaders",
                30,
                3000,
                browser_identity="browser-1",
                context_index=0,
            )

        self.assertTrue(first_page.closed)
        self.assertIs(result[0], second_page)
        self.assertEqual(result[3], ["Chrome CDP 首次直达内容无效：HTML 长度过短：13", "已预热"])
        self.assertEqual(open_page.call_count, 2)
        warm_up.assert_called_once()

    def test_playwright_uses_page_specific_render_wait(self) -> None:
        class FakePage:
            def close(self) -> None:
                return None

        valid_html = "<html><body>" + ("有效正文" * 800) + "</body></html>"
        with (
            patch("crawler_core.fetcher.is_configured_python", return_value=True),
            patch(
                "crawler_core.fetcher.get_thread_playwright_context",
                return_value=object(),
            ) as get_context,
            patch(
                "crawler_core.fetcher.open_rendered_page",
                return_value=(FakePage(), valid_html, "https://example.com/leaders"),
            ) as open_page,
        ):
            result = fetch_by_playwright(
                "https://example.com/leaders",
                timeout=30,
                render_wait_ms=7000,
            )

        self.assertEqual(result.collector, "playwright")
        self.assertEqual(get_context.call_args.kwargs["timeout_seconds"], 30)
        self.assertEqual(open_page.call_args.args[3], 7000)


class RunnerContextTests(unittest.TestCase):
    """验证公共运行器在不改变Path返回值的情况下传回实际采集事实。"""

    def test_runtime_context_contains_actual_collector(self) -> None:
        fake_result = FetchResult(
            html="<html><body>测试</body></html>",
            final_url="https://www.cutech.edu.cn/center/20-24",
            collector="playwright",
            warnings=[],
            execution_mode="subprocess",
            attempted_collectors=["playwright(in_process):失败", "playwright(subprocess):成功"],
        )
        runtime_context: dict[str, object] = {}

        def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
            _ = html, final_url, page_rule
            return [{"name": "测试人员", "duty": "测试职务"}]

        with tempfile.TemporaryDirectory() as temporary_dir:
            with (
                patch("crawler_core.runner.fetch_html_for_rule", return_value=(fake_result, None)),
                patch("crawler_core.runner.record_fetch_success"),
            ):
                output_path = run_page_adapter(
                    {"rule_id": "0051", "fetch_mode": "playwright", "_fetch_mode_override": True},
                    {"__file__": __file__, "parse_page": parse_page},
                    Path(temporary_dir),
                    runtime_context=runtime_context,
                )

        self.assertIsInstance(output_path, Path)
        self.assertEqual(runtime_context["actual_collector"], "playwright")
        self.assertEqual(runtime_context["execution_mode"], "subprocess")
        self.assertTrue(runtime_context["extraction_succeeded"])

    def test_page_rule_propagates_browser_render_wait(self) -> None:
        fake_result = FetchResult(
            html="<html><body>测试</body></html>",
            final_url="https://example.com/leaders",
            collector="playwright",
            warnings=[],
        )
        with patch(
            "crawler_core.runner.fetch_html_with_strategy",
            return_value=fake_result,
        ) as fetch:
            result, snapshot_path = fetch_html_for_rule(
                {
                    "url": "https://example.com/leaders",
                    "fetch_mode": "playwright",
                    "browser_render_wait_ms": 7000,
                },
                Path("."),
                timeout_seconds=30,
            )

        self.assertIs(result, fake_result)
        self.assertIsNone(snapshot_path)
        self.assertEqual(fetch.call_args.kwargs["browser_render_wait_ms"], 7000)

    def test_inline_parser_can_explicitly_own_fetching(self) -> None:
        with patch("crawler_core.runner.fetch_html_with_strategy") as fetch:
            result, snapshot_path = fetch_html_for_rule(
                {
                    "url": "https://example.com/api-backed-page",
                    "inline_parser_handles_fetch": True,
                    "inline_fetch_collector": "requests",
                },
                Path("."),
                timeout_seconds=30,
            )

        fetch.assert_not_called()
        self.assertEqual(result.html, "")
        self.assertEqual(result.final_url, "https://example.com/api-backed-page")
        self.assertEqual(result.collector, "requests")
        self.assertEqual(result.attempted_collectors, ["requests(inline_parser):执行"])
        self.assertIsNone(snapshot_path)


class PreferredCollectorFallbackTests(unittest.TestCase):
    """验证历史成功采集器失效后仍会继续全局降级链路。"""

    def test_remembered_requests_failure_falls_back_to_playwright(self) -> None:
        valid_html = "<html><body>" + ("有效正文" * 800) + "</body></html>"
        playwright_result = FetchResult(
            html=valid_html,
            final_url="https://example.com/leaders",
            collector="playwright",
            warnings=[],
            attempted_collectors=["playwright(in_process):成功"],
        )

        def fake_fetch(url: str, strategy: str, **kwargs: object) -> FetchResult:
            _ = url, kwargs
            if strategy in {"requests", "raw_http"}:
                raise RuntimeError(f"{strategy} unavailable")
            if strategy == "playwright":
                return playwright_result
            raise AssertionError(f"不应继续执行：{strategy}")

        with patch("crawler_core.fetcher.fetch_html_with_strategy", side_effect=fake_fetch):
            result = fetch_html_with_preferred_fallback(
                "https://example.com/leaders",
                preferred_strategy="requests",
                timeout=10,
            )

        self.assertEqual(result.collector, "playwright")
        self.assertEqual(
            result.attempted_collectors,
            ["requests:失败", "raw_http:失败", "playwright(in_process):成功"],
        )

    def test_visible_gateway_error_is_rejected(self) -> None:
        gateway_html = "<html><body><h1>502 Bad Gateway</h1>" + ("网关错误" * 800) + "</body></html>"

        def fake_fetch(url: str, strategy: str, **kwargs: object) -> FetchResult:
            _ = url, kwargs
            if strategy != "chrome":
                raise RuntimeError(f"{strategy} unavailable")
            return FetchResult(
                html=gateway_html,
                final_url="https://example.com/leaders",
                collector="chrome_cdp",
                warnings=[],
            )

        with patch("crawler_core.fetcher.fetch_html_with_strategy", side_effect=fake_fetch):
            with self.assertRaisesRegex(RuntimeError, "Bad Gateway"):
                fetch_html_with_preferred_fallback(
                    "https://example.com/leaders",
                    preferred_strategy="requests",
                    timeout=10,
                )


class DetailConcurrencyTests(unittest.TestCase):
    """验证详情页并发完成顺序不会改变网页原始人物顺序。"""

    def test_parallel_detail_results_restore_source_order(self) -> None:
        links = [
            DetailLink("甲", "https://example.com/slow.html", "a[href]", "甲"),
            DetailLink("乙", "https://example.com/fast.html", "a[href]", "乙"),
        ]

        def fake_fetch(url: str, **kwargs: object) -> FetchResult:
            _ = kwargs
            if "slow" in url:
                time.sleep(0.03)
            return FetchResult(html=url, final_url=url, collector="raw_http", warnings=[])

        def fake_parse(
            rule: dict[str, object],
            html: str,
            final_url: str,
            snapshot_path: Path | None,
        ) -> list[PersonRecord]:
            _ = rule, html, snapshot_path
            name = "甲" if "slow" in final_url else "乙"
            return [
                PersonRecord(
                    organization="测试机构",
                    url="https://example.com/list.html",
                    name=name,
                    duty="测试职务",
                )
            ]

        with (
            patch("crawler_core.detail_links.collect_detail_links", return_value=links),
            patch("crawler_core.detail_links.fetch_html_with_strategy", side_effect=fake_fetch),
            patch("crawler_core.parser_registry.parse_with_registered_parser", side_effect=fake_parse),
        ):
            records = parse_detail_chain_records(
                {
                    "organization": "测试机构",
                    "url": "https://example.com/list.html",
                    "detail_strategy": {"detail_max_workers": 2},
                },
                "<html></html>",
                "https://example.com/list.html",
                None,
                10,
            )

        self.assertEqual([record.name for record in records], ["甲", "乙"])


class BatchRunnerTimeoutTests(unittest.TestCase):
    """验证一键脚本把总截止时间传播到进程内采集线程。"""

    def test_in_process_attempt_uses_fetch_deadline(self) -> None:
        batch_script = Path(__file__).resolve().parents[2] / "script2-爬取1-一键运行全部爬虫脚本.py"
        module_globals = runpy.run_path(str(batch_script))
        run_with_timeout = module_globals["run_page_rule_once_with_timeout"]

        def fake_run_page_rule_once(*args: object) -> None:
            _ = args
            time.sleep(0.02)
            remaining_fetch_timeout(30)

        run_with_timeout.__globals__["run_page_rule_once"] = fake_run_page_rule_once
        with self.assertRaisesRegex(TimeoutError, "单脚本总运行超时"):
            run_with_timeout(Path("adapter.py"), Path("outputs"), "chrome", 1, 0.01)

    def test_deterministic_failures_do_not_enter_browser(self) -> None:
        batch_script = Path(__file__).resolve().parents[2] / "script2-爬取1-一键运行全部爬虫脚本.py"
        module_globals = runpy.run_path(str(batch_script))
        result_class = module_globals["ScriptRunResult"]
        quality_class = module_globals["OutputQuality"]
        decide_transition = module_globals["decide_failure_transition"]

        not_found_result = result_class(
            False,
            "404 Client Error: Not Found",
            "http_404",
            0.1,
            quality_class(),
        )
        not_found_transition = decide_transition(
            not_found_result,
            Path("adapter.py"),
            "raw_http",
        )
        self.assertTrue(not_found_transition.terminal)
        self.assertEqual(not_found_transition.allowed_modes, ())

        parse_result = result_class(
            False,
            "输出质量问题：解析结果为空",
            "empty_parse",
            0.1,
            quality_class(issue="解析结果为空"),
        )
        parse_transition = decide_transition(
            parse_result,
            Path("missing-static-adapter.py"),
            "requests",
        )
        self.assertTrue(parse_transition.terminal)

    def test_http_5xx_continues_to_later_collectors(self) -> None:
        batch_script = Path(__file__).resolve().parents[2] / "script2-爬取1-一键运行全部爬虫脚本.py"
        module_globals = runpy.run_path(str(batch_script))
        result_class = module_globals["ScriptRunResult"]
        quality_class = module_globals["OutputQuality"]
        decide_transition = module_globals["decide_failure_transition"]

        server_error_result = result_class(
            False,
            "503 Server Error: Service Unavailable",
            "http",
            0.1,
            quality_class(),
        )
        raw_transition = decide_transition(
            server_error_result,
            Path("adapter.py"),
            "raw_http",
        )
        requests_transition = decide_transition(
            server_error_result,
            Path("adapter.py"),
            "requests",
        )
        chrome_transition = decide_transition(
            server_error_result,
            Path("adapter.py"),
            "chrome",
        )

        self.assertFalse(raw_transition.terminal)
        self.assertEqual(raw_transition.allowed_modes, ("requests", "playwright", "chrome"))
        self.assertFalse(requests_transition.terminal)
        self.assertEqual(requests_transition.allowed_modes, ("playwright", "chrome"))
        self.assertTrue(chrome_transition.terminal)

    def test_attempt_timeout_preserves_later_collector_budget(self) -> None:
        batch_script = Path(__file__).resolve().parents[2] / "script2-爬取1-一键运行全部爬虫脚本.py"
        module_globals = runpy.run_path(str(batch_script))
        resolve_attempt_timeout = module_globals["resolve_attempt_timeout_seconds"]
        timeout_by_mode = {
            "raw_http": 90,
            "requests": 90,
            "playwright": 150,
            "chrome": 180,
        }

        self.assertEqual(resolve_attempt_timeout("raw_http", 480, 0.0, timeout_by_mode), 90)
        self.assertEqual(resolve_attempt_timeout("playwright", 480, 181.5, timeout_by_mode), 150)
        self.assertEqual(resolve_attempt_timeout("chrome", 480, 420.2, timeout_by_mode), 59)

    def test_failure_report_uses_final_structured_category(self) -> None:
        batch_script = Path(__file__).resolve().parents[2] / "script2-爬取1-一键运行全部爬虫脚本.py"
        module_globals = runpy.run_path(str(batch_script))
        result_class = module_globals["ScriptRunResult"]
        quality_class = module_globals["OutputQuality"]
        diagnose_failure = module_globals["diagnose_failure_detail"]

        result = result_class(
            False,
            "旧尝试包含 status=404\n--- 重试链路 ---\n当前页面完成抓取但校验失败",
            "page_validation",
            1.0,
            quality_class(issue="抽取失败：人物详情现任信息无法核对"),
        )

        failure_code, _ = diagnose_failure(result)
        self.assertEqual(failure_code, "page_validation_failed")

    def test_success_report_distinguishes_vision_extraction(self) -> None:
        batch_script = Path(__file__).resolve().parents[2] / "script2-爬取1-一键运行全部爬虫脚本.py"
        module_globals = runpy.run_path(str(batch_script))
        result_class = module_globals["ScriptRunResult"]
        quality_class = module_globals["OutputQuality"]
        describe_channel = module_globals["describe_extraction_channel"]

        vision_result = result_class(
            True,
            "完成",
            "",
            1.0,
            quality_class(complete_count=2),
            fetch_mode="llm_vision",
            actual_collector="requests",
            attempted_collectors=["requests:成功", "llm_vision:成功"],
        )
        regular_result = result_class(
            True,
            "完成",
            "",
            1.0,
            quality_class(complete_count=2),
            fetch_mode="requests",
            actual_collector="requests",
            attempted_collectors=["requests:成功"],
        )

        self.assertEqual(describe_channel(vision_result), "deepseek_vision")
        self.assertEqual(describe_channel(regular_result), "deterministic_parser")

    def test_chrome_worker_count_is_forced_to_one(self) -> None:
        batch_script = Path(__file__).resolve().parents[2] / "script2-爬取1-一键运行全部爬虫脚本.py"
        module_globals = runpy.run_path(str(batch_script))
        worker_count = module_globals["worker_count_for_fetch_mode"]
        self.assertEqual(worker_count("chrome", 20, 100), 1)

    def test_hard_timeout_terminates_isolated_process(self) -> None:
        batch_script = Path(__file__).resolve().parents[2] / "script2-爬取1-一键运行全部爬虫脚本.py"
        module_globals = runpy.run_path(str(batch_script))
        run_with_hard_timeout = module_globals["run_page_rule_once_with_hard_timeout"]

        class FakeQueue:
            def close(self) -> None:
                return None

            def join_thread(self) -> None:
                return None

        class FakeProcess:
            def __init__(self) -> None:
                self.terminated = False

            def start(self) -> None:
                return None

            def join(self, timeout: float) -> None:
                _ = timeout

            def is_alive(self) -> bool:
                return not self.terminated

            def terminate(self) -> None:
                self.terminated = True

        fake_process = FakeProcess()

        class FakeContext:
            def Queue(self, maxsize: int) -> FakeQueue:
                _ = maxsize
                return FakeQueue()

            def Process(self, **kwargs: object) -> FakeProcess:
                _ = kwargs
                return fake_process

        with patch.object(
            run_with_hard_timeout.__globals__["multiprocessing"],
            "get_context",
            return_value=FakeContext(),
        ):
            run_result, module_result = run_with_hard_timeout(
                Path("adapter.py"),
                Path("outputs"),
                "chrome",
                1,
                1,
            )

        self.assertFalse(run_result.success)
        self.assertEqual(run_result.failure_category, "timeout")
        self.assertTrue(fake_process.terminated)
        self.assertIsNone(module_result)

    def test_parent_process_writes_failure_output_when_worker_has_none(self) -> None:
        batch_script = Path(__file__).resolve().parents[2] / "script2-爬取1-一键运行全部爬虫脚本.py"
        module_globals = runpy.run_path(str(batch_script))
        ensure_failure_output = module_globals["ensure_failure_output"]
        result_class = module_globals["ScriptRunResult"]
        quality_class = module_globals["OutputQuality"]

        with tempfile.TemporaryDirectory() as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            script_path = temp_dir / "0123_测试机构.py"
            output_dir = temp_dir / "outputs"
            script_path.write_text(
                "PAGE_RULE = {\n"
                "    'rule_id': '0123',\n"
                "    'organization': '测试机构',\n"
                "    'url': 'https://example.com/leaders',\n"
                "}\n",
                encoding="utf-8",
            )
            run_result = result_class(
                False,
                "运行硬超时：chrome 阶段超过 180 秒，隔离进程已终止",
                "timeout",
                180.0,
                quality_class(),
            )

            with patch(
                "crawler_core.business_sources.apply_business_source",
                side_effect=lambda rule: rule,
            ):
                ensure_failure_output(run_result, script_path, output_dir)

            output_path = output_dir / "0123_测试机构.txt"
            self.assertTrue(output_path.is_file())
            lines = output_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines[0].split("\t")), 12)
            self.assertIn("抽取失败：运行硬超时", lines[1])
            self.assertEqual(run_result.quality.output_path, str(output_path))
            self.assertEqual(run_result.quality.failure_record_count, 1)


class VisionProviderPolicyTests(unittest.TestCase):
    """防止已经退出的第三方视觉OCR链路重新进入生产源码。"""

    def test_active_sources_only_use_deepseek_vision_pipeline(self) -> None:
        project_dir = Path(__file__).resolve().parents[2]
        banned_terms = ("千" + "问", "q" + "wen", "dash" + "scope", "ocr" + "_llm")
        active_roots = (
            project_dir / "crawler_core",
            project_dir / "site_adapters",
            project_dir / "workspace" / "tools",
            project_dir / "workspace" / "prompts",
        )
        violations: list[str] = []
        for root in active_roots:
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in {".py", ".txt"}:
                    continue
                content = path.read_text(encoding="utf-8-sig", errors="ignore").lower()
                if any(term.lower() in content or term.lower() in path.name.lower() for term in banned_terms):
                    violations.append(str(path.relative_to(project_dir)))
        self.assertEqual(violations, [])

        self.assertTrue((project_dir / "crawler_core" / "deepseek_vision.py").is_file())
        self.assertTrue((project_dir / "crawler_core" / "vision_llm.py").is_file())
        self.assertTrue(
            (
                project_dir
                / "workspace"
                / "prompts"
                / "DeepSeek视觉人物抽取_v1.txt"
            ).is_file()
        )


def main(verbosity: int) -> None:
    """运行本文件中的全部单元测试。"""
    unittest.main(verbosity=verbosity)


if __name__ == "__main__":
    verbosity_value = 2
    main(verbosity_value)
