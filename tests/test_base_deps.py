"""Base-deps isolation: importing fluvilog must not pull in the API stack."""

import subprocess
import sys
import textwrap


def test_import_fluvilog_does_not_load_fastapi() -> None:
    code = (
        "import sys, fluvilog; "
        "assert 'fastapi' not in sys.modules, "
        "sorted(m for m in sys.modules if 'fastapi' in m)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_serve_api_without_extra_prints_hint() -> None:
    script = textwrap.dedent(
        """
        import sys

        class _Block:
            def find_spec(self, name, path=None, target=None):
                if name.split(".")[0] in {"fastapi", "uvicorn"}:
                    raise ModuleNotFoundError(name)
                return None

        sys.meta_path.insert(0, _Block())
        from fluvilog.cli import main
        sys.exit(main(["serve-api"]))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "fluvilog[api]" in result.stderr
