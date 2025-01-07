# [nuitka_simple_gui](https://github.com/ClericPy/nuitka_simple_gui)

[![PyPI](https://img.shields.io/pypi/v/nuitka_simple_gui?style=plastic)](https://pypi.org/project/nuitka_simple_gui/)![PyPI - Wheel](https://img.shields.io/pypi/wheel/nuitka_simple_gui?style=plastic)


> `pip install nuitka_simple_gui`
> 
> run `python -m nuitka_simple_gui` or `nuitka_simple_gui`

A simple GUI app of nuitka

1. Features
   1. Build python code into executable files with **nuitka**
   2. Shortcut buttons for common usages
   3. Compress folder to a zip file
   4. Add a symbolic link for start.exe
   5. Dependency and source code separation, only build the source code
   6. add `onefile` mode(`2023.07.18`)
   7. add `beep` after finished on windows(`2023.07.18`)
   7. add `dump-config` `load-config`(`2023.07.27`)
   8. other changes view changelogs below
2. User manual
   1. GUI apps do not need docs.
3. Documentation?
   1. GUI apps do not need docs.
4. What's More?
   1. I think about it


### Screenshot

![demo.png](https://raw.githubusercontent.com/ClericPy/nuitka_simple_gui/master/demo.png)

### Changelog

- 2025.1.7
  - add `nuitka_cache` button, show `NUITKA_CACHE_DIR`
  - add `--jobs`
- 2025.1.6
  - add tooltip to plugin checkbox
  - mv ensure_python_path log to GUI textarea, for downloading gcc manually
- 2025.01.05
  - Fix failure when pip_args is empty
  - Change Nuitka plugin list to be dynamically obtained
