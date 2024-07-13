import itertools
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import traceback
import zipfile
from pathlib import Path

import FreeSimpleGUI as sg

__version__ = "2024.02.22"
old_stderr = sys.stderr
_sys = platform.system()
IS_WIN32 = _sys == "Windows"
IS_MAC = _sys in {"OSX", "Darwin"}
IS_LINUX = _sys == "Linux"
_plugins_list = [
    "anti-bloat",
    "pylint-warnings",
    "data-files",
    "dill-compat",
    "enum-compat",
    "eventlet",
    "gevent",
    "gi",
    "glfw",
    "implicit-imports",
    "kivy",
    "matplotlib",
    "multiprocessing",
    "numpy",
    "pbr-compat",
    "pkg-resources",
    "pmw-freezer",
    "pyside6",
    "pyqt5",
    "pyside2",
    "pyqt6",
    "pywebview",
    "tensorflow",
    "tk-inter",
    "torch",
    "trio",
    "pyzmq",
]
plugins = {i: False for i in sorted(_plugins_list)}
cmd_list: list = []
pip_args: list = []
pip_cmd: list = []
file_path: Path = Path("app")
output_path = Path("./nuitka_output")
STOPPING_PROC = False
RUNNING_PROC: subprocess.Popen = None
values_cache: dict = {}
python_exe_path = Path(sys.executable).as_posix()
if python_exe_path.endswith("pythonw"):
    python_exe_path = python_exe_path[:-1]
elif python_exe_path.endswith("pythonw.exe"):
    python_exe_path = python_exe_path[:-5] + ".exe"
non_cmd_events = {"dump_config", "load_config", "--onefile-tempdir-spec"}
non_cmd_prefix = "____"
window: sg.Window = None


def get_ccache_info():
    url = "https://github.com/ccache/ccache/releases"
    with subprocess.Popen(
        ["ccache", "--version"],
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ) as proc:
        text = (
            proc.stdout.readline().decode(sys.getdefaultencoding(), "replace").strip()
        )
        if "ccache version" in text:
            return text
        else:
            return f"ccache not found. Download from:\n{url}"


def ensure_python_path():
    global python_exe_path
    while True:
        title = ""
        msg = ""
        try:
            output = b""
            with subprocess.Popen(
                [python_exe_path, "-m", "nuitka", "--version"],
                stdout=subprocess.PIPE,
                stdin=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            ) as proc:
                yield "start"
                for line in proc.stdout:
                    output += line
                    if b"Is it OK to download and put it in" in line:
                        break
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            output = b""
        text = output.decode(sys.getdefaultencoding(), "replace")
        text = re.sub(r"[\r\n]+", "\n", text)
        if text:
            window["output"].update(f"Nuitka version: {text}\n{get_ccache_info()}")
            gcc_ready = "Is it OK to download and put it in" not in text
            if not gcc_ready:
                title = "Missing gcc"
                msg = (
                    text
                    + f"\nYou need to install gcc before press OK(or close to quit):\n\n{python_exe_path} -m nuitka --version\n"
                )
        if not title:
            nuitka_ready = bool(re.match(r"^[.0-9]+[\r\n]+", text))
            if nuitka_ready:
                return True
            else:
                title = "Missing nuitka"
                msg = (
                    text
                    + f"\nYou need to install nuitka before press OK(or close to quit):\n\n{python_exe_path} -m pip install nuitka\n"
                )
        _python_exe_path = sg.popup_get_file(
            msg + "\nor choose a new Python Interpreter",
            title,
            default_path=python_exe_path,
        )
        if _python_exe_path is None:
            quit()
        path = Path(_python_exe_path)
        if path.is_file():
            python_exe_path = path.as_posix()
        else:
            python_exe_path = _python_exe_path


def slice_by_size(seq, size):
    for it in zip(*(itertools.chain(seq, [...] * size),) * size):
        if ... in it:
            it = tuple(i for i in it if i is not ...)
        if it:
            yield it


def input_path(text, key, action=sg.FileBrowse, disable_input=False):
    return [
        sg.Text(
            text,
            size=(10, None),
        ),
        sg.InputText(key=key, enable_events=True, disabled=disable_input),
        action(
            key=f"{non_cmd_prefix}{key}",
            target=key,
            enable_events=True,
        ),
    ]


def init_checkbox():
    return [
        [
            [
                sg.Radio(
                    "--standalone",
                    group_id="module",
                    key="--standalone",
                    default=True,
                    enable_events=True,
                ),
                sg.Radio(
                    "--module", group_id="module", key="--module", enable_events=True
                ),
                sg.Checkbox(
                    "--windows-disable-console",
                    key="--windows-disable-console",
                    enable_events=True,
                )
                if IS_WIN32
                else [],
                sg.InputText(
                    key="--windows-icon",
                    enable_events=True,
                    visible=False,
                ),
                sg.FileBrowse(
                    button_text="--windows-icon",
                    key=f"{non_cmd_prefix}--windows-icon",
                    target="--windows-icon",
                    enable_events=True,
                )
                if IS_WIN32
                else [],
                sg.Checkbox(
                    "--macos-disable-console",
                    key="--macos-disable-console",
                    enable_events=True,
                )
                if IS_MAC
                else [],
            ],
            sg.Checkbox(
                "--nofollow-imports",
                default=True,
                key="--nofollow-imports",
                enable_events=True,
            ),
            sg.Checkbox(
                "--remove-output",
                key="--remove-output",
                default=True,
                enable_events=True,
            ),
            sg.Checkbox(
                "--no-pyi-file", key="--no-pyi-file", default=True, enable_events=True
            ),
        ],
        [
            sg.Radio(
                "--mingw64",
                group_id="build_tool",
                key="--mingw64",
                enable_events=True,
            ),
            sg.Radio(
                "--clang", group_id="build_tool", key="--clang", enable_events=True
            ),
            sg.Radio(
                "None", default=True, group_id="build_tool", key="", enable_events=True
            ),
            sg.Checkbox(
                "--assume-yes-for-downloads",
                key="--assume-yes-for-downloads",
                default=True,
                enable_events=True,
            ),
        ],
        [
            sg.Frame(
                "Plugins",
                [
                    [
                        sg.Checkbox(i, key="_plugin_%s" % i, enable_events=True)
                        for i in ii
                    ]
                    for ii in slice_by_size(plugins, 6)
                ],
            )
        ],
    ]


def update_disabled(k, v):
    if k == "--onefile":
        window["--onefile-tempdir-spec"].update(disabled=not v)
        window["is_compress"].update(disabled=v)
        window["need_start_file"].update(disabled=v)


def update_cmd(event, values):
    # print(values)
    global file_path, output_path
    cmd = [
        python_exe_path,
        "-m",
        "nuitka",
    ]
    for k, v in values.items():
        k = str(k)
        update_disabled(k, v)
        if k == "--onefile":
            if v:
                cmd.append(k)
                if values["--onefile-tempdir-spec"]:
                    p = values["--onefile-tempdir-spec"]
                    cmd.append(f"--onefile-tempdir-spec={p}")
            continue
        elif k in non_cmd_events or k.startswith(non_cmd_prefix):
            continue
        if v:
            if k.startswith("--"):
                if k in {"--include-package", "--include-module"}:
                    for _value in v.split():
                        cmd.append(f"{k}={_value}")
                elif k == "--windows-icon":
                    p = Path(v).as_posix()
                    if p.endswith(".exe"):
                        # exe may not work
                        cmd.append(f"--windows-icon-from-exe={p}")
                    elif p.endswith(".ico"):
                        cmd.append(f"--windows-icon-from-ico={p}")
                    else:
                        cmd.append(f"--windows-icon-from-ico={p}")
                elif k == "--output-dir":
                    output_path = Path(v)
                    cmd.append(f"--output-dir={output_path.as_posix()}")
                elif k == "--output-filename":
                    _name = v.replace('"', "_").replace(" ", "_").replace("'", "_")
                    cmd.append(f"--output-filename={_name}")
                    if event == k:
                        window["--onefile-tempdir-spec"].update(f"./{_name}_cache")
                elif k == "--other-args":
                    cmd.append(v)
                else:
                    cmd.append(k)
            elif k == "file_path":
                file_path = Path(v)
                if event == k:
                    window["--output-filename"].update(file_path.stem)
                    window["--onefile-tempdir-spec"].update(f"./{file_path.stem}_cache")
            elif k == "pip_args":
                if event == k and Path(v).is_file():
                    v = f"-r {v}"
                    window["pip_args"].update(v)
                args = v.split()
                pip_args.clear()
                pip_args.extend(args)
                pip_cmd.clear()
                pip_cmd.extend(
                    [
                        python_exe_path,
                        "-m",
                        "pip",
                        "install",
                    ]
                )
                pip_cmd.extend(pip_args)
                pips_path = (output_path / f"{file_path.stem}.pips").as_posix()
                pip_cmd.extend(["-t", pips_path])
                cmd.append(f"--include-data-dir={pips_path}=./")
        else:
            if k == "pip_args":
                pip_cmd.clear()
    if IS_WIN32:
        from importlib.util import find_spec

        if find_spec("pywin32_bootstrap") is not None:
            cmd.extend(["--include-module=pywin32_bootstrap"])
    for k, v in plugins.items():
        if v:
            cmd.append("--enable-plugin=%s" % k)
    cmd.append(file_path.as_posix())
    # print(subprocess.list2cmdline(cmd))
    text = f"[Python]:\n{sys.version}\n[Build]"
    if pip_cmd:
        text += "\n" + subprocess.list2cmdline(pip_cmd)
    text += "\n" + subprocess.list2cmdline(cmd)

    window["output"].update(text + f'\n{"- " * 50}')
    cmd_list.clear()
    cmd_list.extend(cmd)


def update_plugin_list(e, items):
    for k, v in items.items():
        if str(k).startswith("_plugin_"):
            key = k[8:]
            plugins[key] = v


def print_sep(text: str):
    print(
        "\n==================== %s ====================\n\n" % text.center(20, " "),
        end="",
        flush=True,
    )


def start_build():
    global RUNNING_PROC, STOPPING_PROC
    window["Start"].update(disabled=True)
    window["Cancel"].update(disabled=False)
    try:
        output_path.mkdir(parents=True, exist_ok=True)
        if pip_args:
            print_sep('"pip install" Start')
            print(pip_args, flush=True)
            RUNNING_PROC = subprocess.Popen(
                pip_cmd,
                # shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            for line in RUNNING_PROC.stdout:
                print(line.decode("utf-8", "replace"), end="", flush=True)
                if STOPPING_PROC:
                    RUNNING_PROC.kill()
                    break
            code = RUNNING_PROC.wait()
            if code != 0:
                raise ValueError("Bad return code: %s" % code)
            print_sep('"pip install" Finished')
        print_sep("Build Start")
        RUNNING_PROC = subprocess.Popen(
            cmd_list,
            shell=True,
            # creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        for line in RUNNING_PROC.stdout:
            print(line.decode("utf-8", "replace"), end="", flush=True)
            if STOPPING_PROC:
                RUNNING_PROC.kill()
                break
        code = RUNNING_PROC.wait()
        if code != 0:
            raise ValueError("Bad return code: %s" % code)
        print_sep("Build Success")
        app_name = file_path.stem
        if values_cache["need_start_file"] and not window["need_start_file"].Disabled:
            with open(output_path / f"{app_name}.bat", "w", encoding="utf-8") as f:
                f.write(f"@echo off\ncd {app_name}.dist\nstart /B {app_name}")
        if values_cache["is_compress"] and not window["is_compress"].Disabled:
            print_sep("Compress Start")
            src_dir = output_path / f"{file_path.stem}.dist"
            if src_dir.is_dir():
                target = output_path / f"{file_path.stem}.zip"
                with zipfile.ZipFile(
                    target, "w", zipfile.ZIP_DEFLATED, compresslevel=9
                ) as zf:
                    for file in src_dir.rglob("*"):
                        zf.write(file, file.relative_to(src_dir.parent))
                    if values_cache["need_start_file"]:
                        zf.write(output_path / f"{app_name}.bat", f"{app_name}.bat")
                print_sep("Compress Finished")
            else:
                print(src_dir.absolute().as_posix(), "is_dir:", src_dir.is_dir())
                print_sep("Compress Skipped")
        print_sep("Mission Completed")
        if IS_WIN32:
            beep()

    except Exception:
        traceback.print_exc()
        print_sep("Error")
    finally:
        shutil.rmtree(
            (output_path / f"{file_path.stem}.pips").as_posix(), ignore_errors=True
        )

    RUNNING_PROC = None
    window["Start"].update(disabled=False)
    window["Cancel"].update(disabled=True)
    STOPPING_PROC = False


def beep():
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    frequency = 800
    duration = 200
    for _ in range(3):
        kernel32.Beep(frequency, duration)


def main():
    ensure_path_gen = ensure_python_path()
    next(ensure_path_gen)
    sg.theme("default1")
    layout = [
        input_path("Entry Point:", "file_path", disable_input=True),
        [
            sg.Text(
                "Output Name:",
                size=(10, None),
            ),
            sg.InputText(
                file_path.stem,
                key="--output-filename",
                size=(10, None),
                enable_events=True,
            ),
            sg.Checkbox(
                "--onefile",
                default=False,
                key="--onefile",
                enable_events=True,
            ),
            sg.Input(
                f"./{file_path.stem}_cache",
                key="--onefile-tempdir-spec",
                size=(30, None),
                tooltip=r"""--onefile-tempdir-spec
%TEMP%	User temporary file directory	C:\Users\...\AppData\Locals\Temp
%PID%	Process ID	2772
%TIME%	Time in seconds since the epoch.	1299852985
%PROGRAM%	Full program run-time filename of executable.	C:\SomeWhere\YourOnefile.exe
%PROGRAM_BASE%	No-suffix of run-time filename of executable.	C:\SomeWhere\YourOnefile
%CACHE_DIR%	Cache directory for the user.	C:\Users\SomeBody\AppData\Local
%COMPANY%	Value given as --company-name	YourCompanyName
%PRODUCT%	Value given as --product-name	YourProductName
%VERSION%	Combination of --file-version & --product-version	3.0.0.0-1.0.0.0
%HOME%	Home directory for the user.	/home/somebody
%NONE%	When provided for file outputs, None is used	see notice below
%NULL%	When provided for file outputs, os.devnull is used	see notice below
""",
                enable_events=True,
                disabled=True,
            ),
        ],
        init_checkbox(),
        [
            sg.Text(
                "--include-package:".ljust(20),
                size=(15, None),
            ),
            sg.Input(
                "",
                key="--include-package",
                tooltip="separate by Space",
                enable_events=True,
            ),
        ],
        [
            sg.Text(
                "--include-module:".ljust(20),
                size=(15, None),
            ),
            sg.Input(
                "",
                key="--include-module",
                tooltip="separate by Space",
                enable_events=True,
            ),
        ],
        [
            sg.Text(
                "Custom Args:".ljust(20),
                size=(15, None),
            ),
            sg.Input("", key="--other-args", enable_events=True),
        ],
        input_path("Pip Args:".ljust(20), "pip_args", sg.FilesBrowse),
        [
            sg.Text(
                "Output Path:",
                size=(10, None),
            ),
            sg.InputText(
                output_path.as_posix(), key="--output-dir", enable_events=True
            ),
            sg.FolderBrowse(target="--output-dir", enable_events=True),
            sg.Button("View") if IS_WIN32 else "",
            sg.Button("Remove"),
        ],
        [
            sg.Button("Start", size=(None, 10)),
            sg.Button("Cancel", disabled=True),
            sg.Button("Quit"),
            sg.Checkbox("Compress", key="is_compress", enable_events=True),
            sg.Checkbox(
                "shortcut.bat",
                key="need_start_file",
                default=False,
                tooltip="Add app.bat for shortcut",
                enable_events=True,
            )
            if IS_WIN32
            else [],
            sg.Button(
                "dump_config",
                key="dump_config",
                enable_events=True,
            ),
            sg.Button(
                "load_config",
                key="load_config",
                enable_events=True,
            ),
        ],
        [
            sg.Output(
                key="output",
                size=(80, 12),
            )
        ],
    ]
    global window
    window = sg.Window(
        "Nuitka Toolkit - v%s on %s" % (__version__, sys.version.split(maxsplit=1)),
        layout,
        # size=(800, 500),
        # font=('', 13),
        resizable=True,
        finalize=True,
    )

    def view_folder(event, values):
        if output_path.is_dir():
            subprocess.run(["explorer", output_path.absolute()])
        else:
            sg.popup_error(f"{output_path} is not a folder.")

    def rm_cache_dir(event, values):
        if output_path.is_dir():
            shutil.rmtree(output_path)

    def kill_proc(event, values):
        def _kill_windows_proc(pid):
            for _ in range(4):
                with subprocess.Popen(
                    f'wmic process where "parentprocessid={pid}" get processid',
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                ) as p:
                    for _pid in re.findall(b"[0-9]+", p.stdout.read()):
                        _kill_windows_proc(int(_pid))
            try:
                os.kill(pid, 9)
            except OSError:
                pass

        global STOPPING_PROC
        if RUNNING_PROC:
            STOPPING_PROC = True
            if IS_WIN32:
                return _kill_windows_proc(RUNNING_PROC.pid)
            for f in [RUNNING_PROC.terminate, RUNNING_PROC.kill]:
                f()
                try:
                    RUNNING_PROC.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    continue

    def dump_config(event, values):
        _path = sg.popup_get_file(
            "Save config.json",
            default_path=(Path.cwd() / "config.json").absolute().as_posix(),
        )
        if not _path:
            return
        path = Path(_path)
        try:
            text = json.dumps(values, ensure_ascii=False, sort_keys=True, indent=2)
            path.write_text(text)
        except Exception:
            sg.popup_error(traceback.format_exc())

    def load_config(event, values):
        _path = sg.popup_get_file(
            "Load config.json",
            default_path=(Path.cwd() / "config.json").absolute().as_posix(),
        )
        if not _path:
            return
        path = Path(_path)
        try:
            values_cache.clear()
            values_cache.update(json.loads(path.read_text()))
            for k, v in values_cache.items():
                # print(type(window[k]), k)
                if isinstance(window[k], sg.Button):
                    continue
                update_disabled(k, v)
                window[k].update(v)
        except Exception:
            sg.popup_error(traceback.format_exc())

    for _ in ensure_path_gen:
        pass

    actions = {
        "View": view_folder,
        "Remove": rm_cache_dir,
        "Cancel": kill_proc,
        "dump_config": dump_config,
        "load_config": load_config,
    }
    error = None
    while True:
        try:
            event, values = window.read()
            if values:
                values_cache.update(values)
            # print(event, values, flush=True, file=old_stderr)
            callback = actions.get(event)
            if callback:
                callback(event, values)
                continue
            if event == sg.WIN_CLOSED or event == "Quit":
                if RUNNING_PROC:
                    RUNNING_PROC.kill()
                    RUNNING_PROC.wait()
                break
            # window['output'].update(values)
            update_plugin_list(event, values)
            update_cmd(event, values)
            if event == "Start" and not RUNNING_PROC:
                threading.Thread(target=start_build, daemon=True).start()
        except BaseException:
            error = traceback.format_exc()
            break
    window.close()
    if error:
        print(error, file=old_stderr, flush=True)
    shutil.rmtree(
        (output_path / f"{file_path.stem}.pips").as_posix(), ignore_errors=True
    )


if __name__ == "__main__":
    main()
