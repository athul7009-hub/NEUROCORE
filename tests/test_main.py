
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.__main__ import main, run_cli, run_directory_scan
from app.core.schemas import ToolStatus


def make_result(
    status=ToolStatus.EXECUTED,
    success=True,
    message="Scan completed.",
    data=None,
):
    return SimpleNamespace(
        status=status,
        success=success,
        message=message,
        data=data or {
            "root": "C:/test",
            "total_files": 3,
            "total_size_bytes": 1024,
            "recoverable_bytes": 512,
            "extension_counts": {".txt": 2, ".py": 1},
            "duplicates": [],
            "scan_warnings": [],
            "hash_skipped": [],
        },
    )


def test_run_directory_scan_rejects_empty_directory(monkeypatch, capsys):
    coordinator = MagicMock()
    monkeypatch.setattr("builtins.input", lambda _: "   ")

    run_directory_scan(coordinator)

    assert "Directory path cannot be empty." in capsys.readouterr().out
    coordinator.execute_tool.assert_not_called()


def test_run_directory_scan_success(monkeypatch, capsys):
    coordinator = MagicMock()
    coordinator.execute_tool.return_value = make_result()

    monkeypatch.setattr("builtins.input", lambda _: "C:/test")

    run_directory_scan(coordinator)

    output = capsys.readouterr().out

    assert "Directory Scan Results" in output
    assert "C:/test" in output
    assert "Total files: 3" in output
    coordinator.execute_tool.assert_called_once()


def test_run_directory_scan_approval_accepted(monkeypatch, capsys):
    coordinator = MagicMock()
    coordinator.execute_tool.side_effect = [
        make_result(
            status=ToolStatus.PROPOSED,
            success=False,
            message="Approval required.",
        ),
        make_result(),
    ]

    inputs = iter(["C:/test", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    run_directory_scan(coordinator)

    output = capsys.readouterr().out

    assert "Approval required" in output
    assert "Directory Scan Results" in output

    coordinator.approve_tool.assert_called_once()
    coordinator.reject_tool.assert_not_called()
    assert coordinator.execute_tool.call_count == 2

    first_request = coordinator.execute_tool.call_args_list[0].args[0]
    coordinator.approve_tool.assert_called_once_with(first_request.action_id)


def test_run_directory_scan_approval_rejected(monkeypatch, capsys):
    coordinator = MagicMock()
    coordinator.execute_tool.return_value = make_result(
        status=ToolStatus.PROPOSED,
        success=False,
        message="Approval required.",
    )

    inputs = iter(["C:/test", "n"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    run_directory_scan(coordinator)

    output = capsys.readouterr().out

    assert "Tool execution rejected." in output
    coordinator.reject_tool.assert_called_once()
    coordinator.approve_tool.assert_not_called()
    assert coordinator.execute_tool.call_count == 1


def test_run_directory_scan_invalid_approval(monkeypatch, capsys):
    coordinator = MagicMock()
    coordinator.execute_tool.return_value = make_result(
        status=ToolStatus.PROPOSED,
        success=False,
        message="Approval required.",
    )

    inputs = iter(["C:/test", "maybe"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    run_directory_scan(coordinator)

    output = capsys.readouterr().out

    assert "Invalid decision." in output
    coordinator.reject_tool.assert_called_once()
    coordinator.approve_tool.assert_not_called()
    assert coordinator.execute_tool.call_count == 1


def test_run_directory_scan_tool_failure(monkeypatch, capsys):
    coordinator = MagicMock()
    coordinator.execute_tool.return_value = make_result(
        success=False,
        message="Directory scan failed.",
    )

    monkeypatch.setattr("builtins.input", lambda _: "C:/test")

    run_directory_scan(coordinator)

    output = capsys.readouterr().out

    assert "Tool execution failed: Directory scan failed." in output


def test_run_directory_scan_execution_exception(monkeypatch, capsys):
    coordinator = MagicMock()
    coordinator.execute_tool.side_effect = RuntimeError("Internal failure")

    monkeypatch.setattr("builtins.input", lambda _: "C:/test")

    run_directory_scan(coordinator)

    output = capsys.readouterr().out

    assert "Tool operation failed." in output
    assert "Internal failure" not in output


def test_run_directory_scan_approval_exception(monkeypatch, capsys):
    coordinator = MagicMock()
    coordinator.execute_tool.return_value = make_result(
        status=ToolStatus.PROPOSED,
        success=False,
    )
    coordinator.approve_tool.side_effect = RuntimeError("Approval failure")

    inputs = iter(["C:/test", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    run_directory_scan(coordinator)

    output = capsys.readouterr().out

    assert "Tool operation failed." in output
    assert "Approval failure" not in output


def test_run_cli_exits(monkeypatch, capsys):
    coordinator = MagicMock()
    monkeypatch.setattr("builtins.input", lambda _: "0")

    run_cli(coordinator)

    assert "NEUROCORE stopped." in capsys.readouterr().out
    coordinator.handle_task.assert_not_called()


def test_main_runs_cli(monkeypatch, capsys):
    runtime = SimpleNamespace(coordinator=MagicMock())
    cli_mock = MagicMock()

    monkeypatch.setattr("app.__main__.create_runtime", lambda: runtime)
    monkeypatch.setattr("app.__main__.run_cli", cli_mock)

    main()

    assert "NEUROCORE initialized successfully." in capsys.readouterr().out
    cli_mock.assert_called_once_with(runtime.coordinator)


def test_main_handles_keyboard_interrupt(monkeypatch, capsys):
    runtime = SimpleNamespace(coordinator=MagicMock())

    monkeypatch.setattr("app.__main__.create_runtime", lambda: runtime)
    monkeypatch.setattr(
        "app.__main__.run_cli",
        MagicMock(side_effect=KeyboardInterrupt),
    )

    main()

    assert "NEUROCORE stopped." in capsys.readouterr().out


def test_main_reports_startup_failure(monkeypatch, capsys):
    monkeypatch.setattr(
        "app.__main__.create_runtime",
        MagicMock(side_effect=RuntimeError("Startup failure")),
    )

    with pytest.raises(RuntimeError, match="Startup failure"):
        main()

    output = capsys.readouterr().out

    assert "NEUROCORE could not start" in output
