# [nuitka_simple_gui](https://github.com/ClericPy/nuitka_simple_gui)

[![PyPI](https://img.shields.io/pypi/v/nuitka_simple_gui?style=plastic)](https://pypi.org/project/nuitka_simple_gui/) ![PyPI - Wheel](https://img.shields.io/pypi/wheel/nuitka_simple_gui?style=plastic)


> `pip install nuitka_simple_gui`
>
> Then just run `python -m nuitka_simple_gui` or `nuitka_simple_gui`
>
> Or use uv `uvx nuitka_simple_gui` (if you have [uv](https://github.com/ultralytics/uv))
>

A simple GUI app for Nuitka.

> **Tip**: On Windows, [Zig](https://ziglang.org/) is recommended as the C compiler — lightweight, no extra setup, and supports Python 3.13+ (which MinGW64 does not yet). Install with:
>
> `pip install nuitka_simple_gui[zig]`

### Optional Dependencies

| Extra | Package | Purpose |
|-------|---------|---------|
| `zig` | `ziglang>=0.16.0` | Use Zig as C compiler (`--zig` / `CC` auto-detect) |

## Features

1. Easily build your Python code into executable files using **Nuitka**
2. Handy shortcut buttons for common tasks
3. Compress folders into zip files
4. Quickly create a symbolic link for `start.exe`
5. Separate dependencies and source code—only build your source code
6. Added `onefile` mode (since 2023.07.18), with `keep cache` option for cached extraction(since 2025.9.23)
7. Added a beep notification after finishing on Windows (since 2023.07.18)
8. Added `dump-config` and `load-config` features (since 2023.07.27)
9. For more changes, check the changelog below
10. Fix Linux & macOS compatibility (since 2025.11.18)
11. Added `--zig` build tool option and `CC` input for custom compiler path, auto-detects [ziglang](https://github.com/nicholasgasior/python-ziglang) (install with `pip install nuitka_simple_gui[zig]`)
12. Added `scan_pips` checkbox: scans `.py` files in `.pips` dir for stdlib imports, auto-fills `--include-package` / `--include-module` to prevent `ModuleNotFoundError` with `--nofollow-imports`

## User Manual

No manual needed—just use the GUI!

## Documentation

No docs needed—just use the GUI!

## What's Next?

I'm still thinking about it. Stay tuned!

---

### WARNING

- On Windows, Nuitka needs a C compiler. You can install [MinGW64](https://nuitka.net/doc/user-manual.html#mingw-windows), [Visual Studio](https://nuitka.net/doc/user-manual.html#visual-c-compiler-windows), or [Zig](https://ziglang.org/) (recommended).
  - If you don't have a C compiler, just run `python -m nuitka --version --assume-yes-for-downloads` and Nuitka will try to download MinGW64 for you automatically.

---

### Screenshot

![demo.png](https://raw.githubusercontent.com/ClericPy/nuitka_simple_gui/master/demo.png)

---

### Changelog

- 2026.5.28
  - Added `--zig` build tool option and `CC` input with auto-detect ziglang support
  - Added optional dependency `pip install nuitka_simple_gui[zig]` (ziglang is no longer required)
  - Added `requires-python >= 3.11` to project metadata
  - Updated `--onefile-tempdir-spec` tooltip with correct `{}` token syntax and new tokens (`PROGRAM_DIR`, `FILE_VERSION`, `PRODUCT_VERSION`)
  - Added warning for Windows zig mode: onefile with relative paths and "keep cache" unchecked may fail
- 2026.1.31
  - Use `--windows-console-mode` dropdown instead of deprecated `--windows-disable-console`
  - Use `--macos-create-app-bundle` instead of deprecated `--macos-disable-console`
  - Added `--macos-app-icon` option for macOS
- 2025.11.21
  - Fixed `--include-data-dir` -> `--include-raw-dir` for nuitka compatibility
  - Updated config load logic
- 2025.11.20
  - Fixed `popup_get_file` for `dump_config`
- 2025.11.18
  - Fixed Linux & macOS compatibility
- 2025.9.23
  - Added a "keep cache" checkbox for `--onefile` mode
- 2025.1.7
  - Added a `nuitka_cache` button to show `NUITKA_CACHE_DIR`
  - Added support for `--jobs`
- 2025.1.6
  - Added tooltips to plugin checkboxes
  - Moved `ensure_python_path` log to the GUI textarea, for manual GCC downloads
- 2025.01.05
  - Fixed a failure when `pip_args` is empty
  - Made the Nuitka plugin list update dynamically
