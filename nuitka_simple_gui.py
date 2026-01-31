import ast
import inspect
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
import typing
import zipfile
from pathlib import Path

import FreeSimpleGUI as sg
from nuitka.plugins.Plugins import loadPlugins, plugin_name2plugin_classes
from nuitka.utils.AppDirs import getCacheDir
from nuitka.utils.Download import getCachedDownloadedMinGW64

__version__ = "2026.01.31"
sg.theme("default1")
old_stderr = sys.stderr
_sys = platform.system()
IS_WIN32 = _sys == "Windows"
IS_MAC = _sys in {"OSX", "Darwin"}
IS_LINUX = _sys == "Linux"
loadPlugins()
_plugins_list = {
    k: getattr(v[0], "plugin_desc", "")
    for k, v in plugin_name2plugin_classes.items()
    if not v[0].isDeprecated()
}
plugins_checkbox = {i: False for i in sorted(_plugins_list)}
cmd_list: list = []
pip_args: list = []
pip_cmd: list = []
file_path: Path = Path("app")
output_path = Path("./nuitka_output")
STOPPING_PROC = False
RUNNING_PROC: typing.Optional[subprocess.Popen] = None
values_cache: dict = {}
python_exe_path = Path(sys.executable).as_posix()
if python_exe_path.endswith("pythonw"):
    python_exe_path = python_exe_path[:-1]
elif python_exe_path.endswith("pythonw.exe"):
    python_exe_path = python_exe_path[:-5] + ".exe"
non_cmd_events = {"dump_config", "load_config", "--onefile-tempdir-spec"}
non_cmd_prefix = "____"
window: sg.Window = None
nuitka_cache_path = Path(getCacheDir("")).absolute()
download_mingw_urls: list = []


def init_download_urls():
    if download_mingw_urls:
        return
    source_code = inspect.getsource(getCachedDownloadedMinGW64)
    tree = ast.parse(source_code)

    class URLExtractor(ast.NodeVisitor):
        def __init__(self):
            self.urls = []

        def visit_Assign(self, node):
            if isinstance(node.targets[0], ast.Name) and node.targets[0].id == "url":
                if isinstance(node.value, ast.Constant) and isinstance(
                    node.value.value, str
                ):
                    self.urls.append(node.value.value)
            self.generic_visit(node)

    extractor = URLExtractor()
    extractor.visit(tree)
    download_mingw_urls.extend(extractor.urls)


def ensure_python_path():
    global python_exe_path
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
            for line in proc.stdout:
                output += line
                if b"Is it OK to download and put it in" in line:
                    break
            proc.terminate()
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        output = b""
    text = output.decode(sys.getdefaultencoding(), "replace")
    text = re.sub(r"[\r\n]+", "\n", text)
    if text:
        gcc_ready = "Is it OK to download and put it in" not in text
        if gcc_ready:
            return f"Nuitka version: {text}"
        else:
            title = "Missing gcc"
            msg = (
                text
                + f"\nTry download gcc?(or close to quit):\n\n{python_exe_path} -m nuitka --version --assume-yes-for-downloads\n"
            )
            print(msg, flush=True)
            if (sg.PopupYesNo(msg, title=title) or "").lower() == "yes":
                try:
                    with subprocess.Popen(
                        [
                            python_exe_path,
                            "-m",
                            "nuitka",
                            "--version",
                            "--assume-yes-for-downloads",
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                    ) as proc:
                        ok = True
                        for line in proc.stdout:
                            text = line.decode("utf-8", "replace")
                            if "Failed to download" in text:
                                ok = False
                            print(text, end="", flush=True)
                    if not ok:
                        raise ValueError(
                            "Failed to download gcc, view the log and download it manually."
                        )
                except (
                    subprocess.TimeoutExpired,
                    FileNotFoundError,
                    Exception,
                ) as e:
                    sg.PopupOK(f"Failed to download gcc {e}")
            else:
                pass
    else:
        quit()


def get_dir_size(path: Path):
    total = 0
    for entry in path.iterdir():
        if entry.is_file():
            total += entry.stat().st_size
        elif entry.is_dir():
            total += get_dir_size(entry)
    return total


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
                sg.Text("--windows-console-mode:", visible=IS_WIN32),
                sg.Combo(
                    ["", "force", "disable", "attach"],
                    default_value="",
                    key="--windows-console-mode",
                    enable_events=True,
                    disabled=not IS_WIN32,
                    visible=IS_WIN32,
                    size=(6, None),
                ),
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
                    disabled=not IS_WIN32,
                    visible=IS_WIN32,
                ),
                sg.Checkbox(
                    "--macos-create-app-bundle",
                    key="--macos-create-app-bundle",
                    enable_events=True,
                    disabled=not IS_MAC,
                    visible=IS_MAC,
                    tooltip="Create a macOS application bundle (no console)",
                ),
                sg.InputText(
                    key="--macos-app-icon",
                    enable_events=True,
                    visible=False,
                ),
                sg.FileBrowse(
                    button_text="--macos-app-icon",
                    key=f"{non_cmd_prefix}--macos-app-icon",
                    target="--macos-app-icon",
                    enable_events=True,
                    disabled=not IS_MAC,
                    visible=IS_MAC,
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
            sg.Checkbox(
                "--no-pyi-file", key="--no-pyi-file", default=True, enable_events=True
            ),
            sg.Text("--jobs:"),
            sg.InputText(
                key="--jobs",
                default_text="",
                tooltip=f"default to {os.cpu_count()}",
                size=(5, None),
                enable_events=True,
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
                        sg.Checkbox(
                            i,
                            key="_plugin_%s" % i,
                            tooltip=_plugins_list.get(i) or "no description",
                            enable_events=True,
                        )
                        for i in ii
                    ]
                    for ii in slice_by_size(plugins_checkbox, 6)
                ],
            )
        ],
    ]


def update_disabled(k, v):
    if k == "--onefile":
        window["--onefile-tempdir-spec"].update(disabled=not v)
        window["is_compress"].update(disabled=v)
        window["need_start_file"].update(disabled=v)
        window["tmp_cached"].update(disabled=not v)


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
                tmp_cached = values.get("tmp_cached", False)
                if tmp_cached:
                    cmd.append("--onefile-cache-mode=cached")
                else:
                    cmd.append("--onefile-cache-mode=temporary")
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
                elif k == "--windows-console-mode":
                    cmd.append(f"--windows-console-mode={v}")
                elif k == "--macos-app-icon":
                    p = Path(v).as_posix()
                    cmd.append(f"--macos-app-icon={p}")
                elif k == "--output-dir":
                    output_path = Path(v)
                    cmd.append(f"--output-dir={output_path.as_posix()}")
                elif k == "--output-filename":
                    _name = v.replace('"', "_").replace(" ", "_").replace("'", "_")
                    cmd.append(f"--output-filename={_name}")
                    if event == k:
                        window["--onefile-tempdir-spec"].update(f"./{_name}_cache")
                elif k == "--other-args":
                    cmd.extend(v.split(","))
                elif k == "--jobs":
                    cmd.append(f"--jobs={v}")
                else:
                    cmd.append(k)
            elif k == "file_path":
                file_path = Path(v)
                if event == k:
                    window["--output-filename"].update(file_path.stem)
                    window["--onefile-tempdir-spec"].update(f"./{file_path.stem}_cache")
            elif k == "pip_args":
                if not v.strip():
                    continue
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
                cmd.append(f"--include-raw-dir={pips_path}=./")
        else:
            if k == "pip_args":
                pip_cmd.clear()
    if IS_WIN32:
        from importlib.util import find_spec

        if find_spec("pywin32_bootstrap") is not None:
            cmd.extend(["--include-module=pywin32_bootstrap"])
    for k, v in plugins_checkbox.items():
        if v:
            cmd.append("--enable-plugin=%s" % k)
    cmd.append(file_path.as_posix())
    # print(subprocess.list2cmdline(cmd))
    text = f"[Python]:\n{sys.version}\n[Build]"
    if pip_cmd:
        text += "\n" + subprocess.list2cmdline(pip_cmd)
    text += "\n" + subprocess.list2cmdline(cmd)

    window["output"].update(text + f"\n{'- ' * 50}")
    cmd_list.clear()
    cmd_list.extend(cmd)


def update_plugin_list(e, items):
    for k, v in items.items():
        if str(k).startswith("_plugin_"):
            key = k[8:]
            plugins_checkbox[key] = v


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
                size=(20, None),
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
            sg.Checkbox(
                "keep cache",
                default=False,
                key="tmp_cached",
                size=(10, None),
                tooltip=r"""
Checked  : `--onefile-cache-mode=tmp_cached`, to keep the tempdir exist;
Unchecked: `--onefile-cache-mode=temporary`, to clear the tempdir after each run;
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
                "Custom Args(,):".ljust(20),
                size=(15, None),
                tooltip="separate by , (comma)",
            ),
            sg.Input(
                "",
                key="--other-args",
                enable_events=True,
                tooltip="separate by , (comma)",
            ),
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
                disabled=not IS_WIN32,
                visible=IS_WIN32,
            ),
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
            sg.Button(
                "nuitka_cache",
                key="nuitka_cache",
                tooltip="Open NUITKA_CACHE_DIR",
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
            save_as=True,
        )
        if not _path:
            return
        path = Path(_path)
        try:
            values["build-system"] = "nuitka_simple_gui"
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
            data = json.loads(path.read_text())
            data.pop("build-system", None)
            values_cache.update(data)
            for k, v in values_cache.items():
                # print(type(window[k]), k)
                ele = window.find_element(k, silent_on_error=True, supress_raise=True)
                if ele is None:
                    continue
                if isinstance(ele, sg.Button):
                    continue
                update_disabled(k, v)
                ele.update(v)
        except Exception:
            sg.popup_error(traceback.format_exc())

    def nuitka_cache(event, values):
        print("\nNUITKA_CACHE_DIR:", os.getenv("NUITKA_CACHE_DIR"), flush=True)
        print("cache_dir:", nuitka_cache_path, flush=True)
        if IS_WIN32:
            proc = subprocess.Popen(["explorer", nuitka_cache_path])
        size = get_dir_size(Path(nuitka_cache_path))
        print(f"{nuitka_cache_path}: {size / 1024**3:.1f} GB", flush=True)
        machine = platform.machine()
        print("platform.machine():", machine)
        if IS_WIN32:
            init_download_urls()
            print(f"Download mingw64({machine}):")
            print("\n".join(download_mingw_urls), flush=True)
            proc.wait()

    actions = {
        "View": view_folder,
        "Remove": rm_cache_dir,
        "Cancel": kill_proc,
        "dump_config": dump_config,
        "load_config": load_config,
        "nuitka_cache": nuitka_cache,
    }
    error = None
    ensure_python_path()
    window.write_event_value("--output-dir", output_path.as_posix())
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
