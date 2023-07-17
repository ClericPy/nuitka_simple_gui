import itertools
import os
import platform
import shutil
import subprocess
import sys
import threading
import traceback
import zipfile
from pathlib import Path

import PySimpleGUI as sg

__version__ = "2023.07.18"
old_stderr = sys.stderr
_sys = platform.system()
IS_WIN32 = _sys == "Windows"
IS_MAC = _sys == "OSX"
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
plugins = {i: False for i in _plugins_list}
cmd_list: list = []
pip_args: list = []
pip_cmd: list = []
file_path: Path = Path("app")
output_path = Path("./nuitka_output")
proc = None
values_cache: dict = {}
python_exe_path = Path(sys.executable).as_posix()
if python_exe_path.endswith("pythonw"):
    python_exe_path = python_exe_path[:-1]
elif python_exe_path.endswith("pythonw.exe"):
    python_exe_path = python_exe_path[:-5] + ".exe"
STOP_PROC = False


def ensure_python_path():

    def check(python):
        try:
            output = subprocess.check_output([python, "-V"], timeout=2)
        except (TimeoutError, FileNotFoundError):
            output = b""
        return output.startswith(b"Python 3.")

    global python_exe_path
    default_python = None
    while 1:
        if check(python_exe_path):
            return
        if default_python is None:
            if check("python"):
                default_python = "python"
            else:
                default_python = ""
        python_exe_path = sg.popup_get_file(
            "Choose a correct Python executable: python / python3 / {Path of Python}",
            "Wrong Python verson",
            default_path=default_python,
        )
        if not python_exe_path:
            quit()


def slice_by_size(seq, size):
    for it in zip(*(itertools.chain(seq, [...] * size),) * size):
        if ... in it:
            it = tuple(i for i in it if i is not ...)
        if it:
            yield it


def input_path(text, key, action=sg.FileBrowse):
    return [
        sg.Text(text),
        sg.InputText(key=key, enable_events=True),
        action(target=(sg.ThisRow, 1), enable_events=True),
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
                sg.Radio("--module",
                         group_id="module",
                         key="--module",
                         enable_events=True),
                sg.Checkbox(
                    "--onefile",
                    default=False,
                    key="--onefile",
                    enable_events=True,
                ),
                sg.Input(
                    "",
                    key="--onefile-tempdir-spec",
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
            sg.Checkbox("--no-pyi-file",
                        key="--no-pyi-file",
                        default=True,
                        enable_events=True),
        ],
        [
            [
                sg.Checkbox(
                    "--windows-disable-console",
                    key="--windows-disable-console",
                    enable_events=True,
                ),
                sg.FileBrowse(
                    "--windows-icon",
                    key="--windows-icon",
                    file_types=(("icon", "*.ico *.exe"),),
                    target=(sg.ThisRow, 1),
                    enable_events=True,
                ),
            ] if IS_WIN32 else [],
            [
                sg.Checkbox(
                    "--macos-disable-console",
                    key="--macos-disable-console",
                    enable_events=True,
                )
            ] if IS_MAC else [],
        ],
        [
            sg.Radio(
                "--mingw64",
                default=True,
                group_id="build_tool",
                key="--mingw64",
                enable_events=True,
            ),
            sg.Radio("--clang",
                     group_id="build_tool",
                     key="--clang",
                     enable_events=True),
            sg.Radio("None", group_id="build_tool", key="", enable_events=True),
        ],
        [
            sg.Frame(
                "Plugins",
                [[
                    sg.Checkbox(i, key="_plugin_%s" % i, enable_events=True)
                    for i in ii
                ]
                 for ii in slice_by_size(plugins, 6)],
            )
        ],
    ]


def update_cmd(window, values):
    # print(values)
    global file_path, output_path
    cmd = [
        python_exe_path,
        "-m",
        "nuitka",
    ]
    for k, v in values.items():
        k = str(k)
        if v:
            if k.startswith("--"):
                if k in {'--onefile-tempdir-spec'}:
                    continue
                elif k == '--onefile':
                    window['--onefile-tempdir-spec'].update(disabled=not v)
                    if v:
                        cmd.append(k)
                        window['--onefile-tempdir-spec'].update(disabled=False)
                        if values['--onefile-tempdir-spec']:
                            p = values["--onefile-tempdir-spec"]
                            cmd.append(f'--onefile-tempdir-spec={p}')
                    else:
                        window['--onefile-tempdir-spec'].update(disabled=True)
                elif k in {"--include-package", "--include-module"}:
                    for _value in v.split():
                        cmd.append(f"{k}={_value}")
                elif k == "--windows-icon":
                    p = Path(v).as_posix()
                    if p.endswith(".exe"):
                        cmd.append(f"--windows-icon-from-exe={p}")
                    elif p.endswith(".ico"):
                        cmd.append(f"--windows-icon-from-ico={p}")
                elif k == "--output-dir":
                    output_path = Path(v)
                    cmd.append(f"--output-dir={output_path.as_posix()}")
                elif k == "--other-args":
                    cmd.append(v)
                else:
                    cmd.append(k)
            elif k == 'file_path':
                file_path = Path(v)
            elif k == "pip_args":
                v_list = v.split(os.path.pathsep)
                args = []
                has_file = False
                for p in v_list:
                    path = Path(p)
                    if path.is_file():
                        args.extend(path.read_text().strip().splitlines())
                        has_file = True
                    else:
                        args.extend(p.split())
                pip_args.clear()
                pip_args.extend(set(args))
                if has_file:
                    window["pip_args"].update(" ".join(pip_args))
                pip_cmd.clear()
                pip_cmd.extend([
                    python_exe_path,
                    "-m",
                    "pip",
                    "install",
                ])
                pip_cmd.extend(pip_args)
                pips_path = (output_path / f"{file_path.stem}.pips").as_posix()
                pip_cmd.extend(["-t", pips_path])
                cmd.append(f"--include-data-dir={pips_path}=./")
        else:
            if k == 'pip_args':
                pip_cmd.clear()
    if IS_WIN32:
        from importlib.util import find_spec
        if find_spec('pywin32_bootstrap') is not None:
            cmd.extend(["--include-module=pywin32_bootstrap"])
    for k, v in plugins.items():
        if v:
            cmd.append("--enable-plugin=%s" % k)
    cmd.append(file_path.as_posix())
    # print(subprocess.list2cmdline(cmd))
    text = f"[Python]:\n{sys.version}\n[Build]"
    if pip_cmd:
        text += "\n" + subprocess.list2cmdline(pip_cmd)
    text += '\n' + subprocess.list2cmdline(cmd)

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
        "\n==================== %s ====================\n\n" %
        text.center(20, " "),
        end="",
        flush=True,
    )


def start_build(window):
    global proc, STOP_PROC
    window["Start"].update(disabled=True)
    window["Cancel"].update(disabled=False)
    try:
        output_path.mkdir(parents=True, exist_ok=True)
        if pip_args:
            print_sep('"pip install" Start')
            print(pip_args, flush=True)
            proc = subprocess.Popen(
                pip_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            for line in proc.stdout:
                print(line.decode("utf-8", "replace"), end="", flush=True)
                if STOP_PROC:
                    proc.kill()
                    break
            code = proc.wait()
            if code != 0:
                raise ValueError("Bad return code: %s" % code)
            print_sep('"pip install" Finished')
        print_sep("Build Start")
        proc = subprocess.Popen(cmd_list,
                                shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        for line in proc.stdout:
            print(line.decode("utf-8", "replace"), end="", flush=True)
            if STOP_PROC:
                proc.kill()
                break
        code = proc.wait()
        if code != 0:
            raise ValueError("Bad return code: %s" % code)
        print_sep("Build Success")
        app_name = file_path.stem
        if values_cache["need_start_file"]:
            with open(output_path / f'{app_name}.bat', 'w',
                      encoding='utf-8') as f:
                f.write(f'@echo off\ncd {app_name}.dist\nstart /B {app_name}')
        if values_cache["is_compress"]:
            print_sep("Compress Start")
            src_dir = output_path / f"{file_path.stem}.dist"
            if src_dir.is_dir():
                target = output_path / f"{file_path.stem}.zip"
                with zipfile.ZipFile(target,
                                     "w",
                                     zipfile.ZIP_DEFLATED,
                                     compresslevel=9) as zf:
                    for file in src_dir.rglob("*"):
                        zf.write(file, file.relative_to(src_dir.parent))
                    if values_cache["need_start_file"]:
                        zf.write(output_path / f"{app_name}.bat",
                                 f"{app_name}.bat")
                print_sep("Compress Finished")
            else:
                print(src_dir.absolute().as_posix(), "is_dir:",
                      src_dir.is_dir())
                print_sep("Compress Skipped")
        print_sep("Mission Completed")
        if IS_WIN32:
            beep()

    except Exception:
        traceback.print_exc()
        print_sep("Error")
    finally:
        shutil.rmtree((output_path / f"{file_path.stem}.pips").as_posix(),
                      ignore_errors=True)

    proc = None
    window["Start"].update(disabled=False)
    window["Cancel"].update(disabled=True)
    STOP_PROC = False


def beep():
    import ctypes
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    frequency = 800
    duration = 200
    for _ in range(3):
        kernel32.Beep(frequency, duration)


def main():
    ensure_python_path()
    sg.theme("default1")
    layout = [
        input_path("Entry Point:", "file_path"),
        init_checkbox(),
        [
            sg.Text("--include-package:".ljust(20)),
            sg.Input(
                "",
                key="--include-package",
                tooltip="separate by Space",
                enable_events=True,
            ),
        ],
        [
            sg.Text("--include-module:".ljust(20)),
            sg.Input(
                "",
                key="--include-module",
                tooltip="separate by Space",
                enable_events=True,
            ),
        ],
        [
            sg.Text("Custom Args:".ljust(20)),
            sg.Input("", key="--other-args", enable_events=True),
        ],
        input_path("Requirements:".ljust(20), "pip_args", sg.FilesBrowse),
        [
            sg.Text("Output Path:"),
            sg.InputText(output_path.as_posix(),
                         key="--output-dir",
                         enable_events=True),
            sg.FolderBrowse(target=(sg.ThisRow, 1), enable_events=True),
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
            ) if IS_WIN32 else [],
        ],
        [sg.Output(
            key="output",
            size=(80, 12),
        )],
    ]

    window = sg.Window(
        "Nuitka Toolkit - v%s on %s" %
        (__version__, sys.version.split(maxsplit=1)),
        layout,
        # size=(800, 500),
        # font=('', 13),
        resizable=True,
        finalize=True,
    )

    # window.maximize()

    def view_folder(event, values):
        if output_path.is_dir():
            subprocess.run(["explorer", output_path.absolute()])
        else:
            sg.popup_error(f"{output_path} is not a folder.")

    def rm_cache_dir(event, values):
        if output_path.is_dir():
            shutil.rmtree(output_path)

    def kill_proc(event, values):
        global STOP_PROC
        if proc:
            STOP_PROC = True
            proc.kill()
            proc.wait()

    actions = {
        "View": view_folder,
        "Remove": rm_cache_dir,
        "Cancel": kill_proc,
    }
    error = None
    while True:
        try:
            event, values = window.read()
            if values:
                values_cache.update(values)
            callback = actions.get(event)
            if callback:
                callback(event, values)
                continue
            # print(event, values, flush=True, file=old_stderr)
            if event == sg.WIN_CLOSED or event == "Quit":
                if proc:
                    proc.kill()
                    proc.wait()
                break
            # window['output'].update(values)
            update_plugin_list(event, values)
            update_cmd(window, values)
            if event == "Start" and not proc:
                threading.Thread(target=start_build,
                                 args=(window,),
                                 daemon=True).start()
        except BaseException:
            error = traceback.format_exc()
            break
    window.close()
    if error:
        print(error, file=old_stderr, flush=True)
    shutil.rmtree((output_path / f"{file_path.stem}.pips").as_posix(),
                  ignore_errors=True)


if __name__ == "__main__":
    main()
