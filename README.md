# [nuitka_simple_gui](https://github.com/ClericPy/nuitka_simple_gui)

[![PyPI](https://img.shields.io/pypi/v/nuitka_simple_gui?style=plastic)](https://pypi.org/project/nuitka_simple_gui/) ![PyPI - Wheel](https://img.shields.io/pypi/wheel/nuitka_simple_gui?style=plastic)


> `pip install nuitka_simple_gui`
>
> Then just run `python -m nuitka_simple_gui` or `nuitka_simple_gui`
>
> Or use uv `uvx nuitka_simple_gui` (if you have [uv](https://github.com/ultralytics/uv))
>

A simple GUI app for Nuitka.

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

## User Manual

No manual needed—just use the GUI!

## Documentation

No docs needed—just use the GUI!

## What's Next?

I'm still thinking about it. Stay tuned!

---

### WARNING

- Nuitka currently supports Python 3.6 to 3.12 (as of 2025-09-23). Python 3.13 is not supported yet.
- On Windows, Nuitka needs a C compiler. You can install [MinGW64](https://nuitka.net/doc/user-manual.html#mingw-windows) or [Visual Studio](https://nuitka.net/doc/user-manual.html#visual-c-compiler-windows).
  - If you don't have a C compiler, just run `python -m nuitka temp.py` and Nuitka will try to download MinGW64 for you automatically.

---

### Screenshot

![demo.png](https://raw.githubusercontent.com/ClericPy/nuitka_simple_gui/master/demo.png)

---

### Changelog

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
