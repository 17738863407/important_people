from __future__ import annotations

import importlib.util
import os
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook


PROJECT_DIR = Path(__file__).resolve().parents[2]


def load_script(filename: str, module_name: str):
    script_path = PROJECT_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upload_mapping_and_in_memory_workbook() -> None:
    module = load_script(
        "script4-职务比对1-上传官员信息.py", "official_update_upload"
    )
    header, rows = module.read_tsv_rows(PROJECT_DIR / "职务规范4：扩充.txt")

    assert header == module.EXPECTED_SOURCE_HEADER
    upload_header, upload_rows = module.select_upload_data(header, rows[:2])
    assert upload_header == [
        "姓名",
        "职务",
        "依据说明",
        "依据链接",
        "排序",
        "所属省",
        "所属市",
    ]

    workbook_bytes = module.generate_excel_bytes(upload_header, upload_rows)
    workbook = load_workbook(BytesIO(workbook_bytes), read_only=True)
    try:
        worksheet = workbook["官员信息"]
        values = list(worksheet.iter_rows(values_only=True))
    finally:
        workbook.close()
    assert list(values[0]) == upload_header
    assert len(values) == len(upload_rows) + 1


def test_upload_uses_playwright_chrome_and_saves_token(
    tmp_path, monkeypatch
) -> None:
    module = load_script(
        "script4-职务比对1-上传官员信息.py", "official_update_upload_playwright"
    )
    chrome_exe = tmp_path / "chrome.exe"
    chrome_exe.write_bytes(b"")
    user_data_dir = tmp_path / ".official_update_chrome_profile"
    token_file = tmp_path / ".secrets" / "official_update_token"
    captured: dict[str, object] = {}

    class FakePage:
        url = "http://example.invalid/official-information"

        def goto(self, url, **kwargs):
            captured["goto"] = (url, kwargs)

        def evaluate(self, expression):
            captured["expression"] = expression
            return "new-token"

    class FakeContext:
        def __init__(self):
            self.pages = [FakePage()]
            self.closed = False

        def new_page(self):
            raise AssertionError("已有后台页面时不应新建页面")

        def close(self):
            self.closed = True

    context = FakeContext()

    class FakeChromium:
        def launch_persistent_context(self, profile, **kwargs):
            captured["profile"] = profile
            captured["launch"] = kwargs
            return context

    class FakePlaywright:
        chromium = FakeChromium()

    class FakePlaywrightManager:
        def __enter__(self):
            captured["temporary_environment"] = {
                name: os.environ.get(name) for name in ("TMPDIR", "TMP", "TEMP")
            }
            return FakePlaywright()

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(module, "sync_playwright", FakePlaywrightManager)
    original_environment = {
        name: os.environ.get(name) for name in ("TMPDIR", "TMP", "TEMP")
    }
    token = module.acquire_browser_token(
        chrome_exe,
        user_data_dir,
        9777,
        "http://example.invalid/official-information",
        "example.invalid",
        "old-token",
        30,
        10,
        token_file,
        TextLogStub(),
    )

    assert token == "new-token"
    assert token_file.read_text(encoding="utf-8") == "new-token"
    assert captured["profile"] == str(user_data_dir)
    launch = captured["launch"]
    assert launch["executable_path"] == str(chrome_exe)
    assert launch["headless"] is False
    assert "--remote-debugging-port=9777" in launch["args"]
    assert launch["timeout"] == 30_000
    assert captured["goto"][0] == "http://example.invalid/official-information"
    assert "downed-officials-token" in captured["expression"]
    assert context.closed is True
    expected_temp_dir = user_data_dir / "playwright-temp"
    assert expected_temp_dir.is_dir()
    assert captured["temporary_environment"] == {
        name: str(expected_temp_dir) for name in ("TMPDIR", "TMP", "TEMP")
    }
    assert {
        name: os.environ.get(name) for name in ("TMPDIR", "TMP", "TEMP")
    } == original_environment


def test_upload_login_timeout_preserves_profile(tmp_path, monkeypatch) -> None:
    module = load_script(
        "script4-职务比对1-上传官员信息.py", "official_update_upload_timeout"
    )
    chrome_exe = tmp_path / "chrome.exe"
    chrome_exe.write_bytes(b"")
    user_data_dir = tmp_path / ".official_update_chrome_profile"
    user_data_dir.mkdir()
    marker = user_data_dir / "profile-marker.txt"
    marker.write_text("KEEP", encoding="utf-8")

    class FakePage:
        url = "http://example.invalid/official-information"

        def goto(self, *_args, **_kwargs):
            pass

    class FakeContext:
        pages = [FakePage()]
        closed = False

        def new_page(self):
            return self.pages[0]

        def close(self):
            self.closed = True

    context = FakeContext()

    class FakeChromium:
        def launch_persistent_context(self, *_args, **_kwargs):
            return context

    class FakePlaywrightManager:
        def __enter__(self):
            return type("FakePlaywright", (), {"chromium": FakeChromium()})()

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(module, "sync_playwright", FakePlaywrightManager)
    try:
        module.acquire_browser_token(
            chrome_exe,
            user_data_dir,
            9777,
            "http://example.invalid/official-information",
            "example.invalid",
            "old-token",
            1,
            0,
            tmp_path / "token",
            TextLogStub(),
        )
    except TimeoutError as error:
        assert "未读取到新令牌" in str(error)
    else:
        raise AssertionError("未取得新令牌时应报告超时")

    assert marker.read_text(encoding="utf-8") == "KEEP"
    assert context.closed is True


class TextLogStub:
    def write(self, _text):
        pass

    def flush(self):
        pass


def test_incomplete_online_fetch_does_not_overwrite(tmp_path, monkeypatch) -> None:
    module = load_script(
        "script4-职务比对2-获取在线比对数据.py", "official_update_fetch"
    )
    output_path = tmp_path / "existing.txt"
    output_path.write_text("KEEP", encoding="utf-8")
    token_file = tmp_path / ".secrets" / "official_update_token"
    token_file.parent.mkdir()
    token_file.write_text("test-token", encoding="utf-8")

    class FakeSession:
        trust_env = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(module.requests, "Session", FakeSession)
    monkeypatch.setattr(module, "fetch_all", lambda *_args: ([{"name": "甲"}], 2, [2]))

    try:
        module.main(
            "http://example.invalid",
            20,
            1,
            output_path,
            tmp_path / "log",
            token_file,
            tmp_path / "chrome.exe",
            tmp_path / "profile",
            9777,
            "http://example.invalid/page",
            "example.invalid",
            1,
            1,
            False,
        )
    except RuntimeError as error:
        assert "抓取不完整" in str(error)
    else:
        raise AssertionError("分页不完整时应拒绝写出结果")

    assert output_path.read_text(encoding="utf-8") == "KEEP"


def test_filter_and_normalize_pipeline(tmp_path) -> None:
    filter_module = load_script(
        "script4-职务比对3-获取无重复数据.py", "official_update_filter"
    )
    normalize_module = load_script(
        "script4-职务比对4-无重复数据规范化.py", "official_update_normalize"
    )

    online_path = tmp_path / "online.txt"
    filtered_path = tmp_path / "filtered.txt"
    filter_log = tmp_path / "filter.log"
    online_path.write_text(
        "\t".join(filter_module.__dict__.get("SPLIT_HEADERS", [
            "姓名", "本地职务", "职级", "排序", "所属省", "所属市", "提醒类型",
            "老数据职务", "依据链接", "需要更新时间", "操作"
        ]))
        + "\n"
        + "甲\t新职务\t正厅级\t1\t北京\t\t需要新增\t旧职务\thttps://a.example\t\t删除\n"
        + "乙\t相同职务\t副厅级\t2\t北京\t\t职务变更\t相同职务\thttps://b.example\t\t删除\n",
        encoding="utf-8",
    )
    filter_module.main(online_path, filtered_path, filter_log)
    filtered_lines = filtered_path.read_text(encoding="utf-8").splitlines()
    assert len(filtered_lines) == 2
    assert filtered_lines[1].startswith("甲\t新职务\t")

    normalized_path = tmp_path / "normalized.txt"
    normalized_path.write_text(
        "姓名*\t职务*\t排序*\t职级*\t所属省*\t所属市\t依据链接\t依据说明\t维护人\t机构\t详情页链接\t脚本序号\n"
        "甲\t新职务\t1\t正厅级\t北京\t\thttps://a.example\t网页信息\t维护员\t北京市人民政府\t\t0001\n",
        encoding="utf-8",
    )
    output_xlsx = tmp_path / "normalized.xlsx"
    normalize_module.main(
        filtered_path,
        normalized_path,
        output_xlsx,
        tmp_path / "normalize.log",
    )

    workbook = load_workbook(output_xlsx, read_only=True)
    try:
        values = list(workbook["无重复排序"].iter_rows(values_only=True))
    finally:
        workbook.close()
    assert len(values) == 2
    assert values[0][0:3] == ("姓名*", "职务*", "老数据职务")
    assert values[1][0:3] == ("甲", "新职务", "旧职务")
