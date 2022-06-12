import itertools
import platform
import shutil
import subprocess
import sys
import threading
import traceback
import zipfile
from pathlib import Path
import os
import PySimpleGUI as sg

old_stderr = sys.stderr
_sys = platform.system()
IS_WIN32 = _sys == 'Windows'
IS_MAC = _sys == 'OSX'
_plugins_list = [
    'anti-bloat', 'pylint-warnings', 'data-files', 'dill-compat', 'enum-compat',
    'eventlet', 'gevent', 'gi', 'glfw', 'implicit-imports', 'kivy',
    'matplotlib', 'multiprocessing', 'numpy', 'pbr-compat', 'pkg-resources',
    'pmw-freezer', 'pyside6', 'pyqt5', 'pyside2', 'pyqt6', 'pywebview',
    'tensorflow', 'tk-inter', 'torch', 'trio', 'pyzmq'
]
plugins = {i: False for i in _plugins_list}
cmd_list = []
pip_args = []
pip_cmd = []
file_path: Path = Path('app')
output_path = Path('./nuitka_output')
proc = None
values_cache = {}


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
            sg.Checkbox('--standalone',
                        key='--standalone',
                        default=True,
                        enable_events=True),
            sg.Checkbox('--nofollow-imports',
                        default=True,
                        key='--nofollow-imports',
                        enable_events=True),
            sg.Checkbox('--remove-output',
                        key='--remove-output',
                        default=True,
                        enable_events=True),
            sg.Checkbox('--no-pyi-file',
                        key='--no-pyi-file',
                        default=True,
                        enable_events=True),
        ],
        [
            [
                sg.Checkbox('--windows-disable-console',
                            key='--windows-disable-console',
                            enable_events=True),
                sg.FileBrowse('--windows-icon',
                              key='--windows-icon',
                              file_types=(("icon", "*.ico *.exe"),),
                              target=(sg.ThisRow, 1),
                              enable_events=True),
            ] if IS_WIN32 else [],
            [
                sg.Checkbox('--macos-disable-console',
                            key='--macos-disable-console',
                            enable_events=True)
            ] if IS_MAC else [],
        ],
        [
            sg.Radio('--mingw64',
                     default=True,
                     group_id='build_tool',
                     key='--mingw64',
                     enable_events=True),
            sg.Radio('--clang',
                     group_id='build_tool',
                     key='--clang',
                     enable_events=True),
            sg.Radio('None', group_id='build_tool', key='', enable_events=True),
        ],
        [
            sg.Frame(
                'Plugins',
                [[
                    sg.Checkbox(i, key='_plugin_%s' % i, enable_events=True)
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
        Path(sys.executable).as_posix(),
        '-m',
        'nuitka',
    ]
    for k, v in values.items():
        k = str(k)
        if v:
            if k.startswith('--'):
                if k in {'--include-package', '--include-module'}:
                    for _value in v.split():
                        cmd.append(f'{k}={_value}')
                elif k == '--windows-icon':
                    p = Path(v).as_posix()
                    if p.endswith('.exe'):
                        cmd.append(f'--windows-icon-from-exe={p}')
                    elif p.endswith('.ico'):
                        cmd.append(f'--windows-icon-from-ico={p}')
                elif k == '--output-dir':
                    output_path = Path(v)
                    cmd.append(f'--output-dir={output_path.as_posix()}')
                elif k == '--other-args':
                    cmd.append(v)
                else:
                    cmd.append(k)
            elif k == 'pip_args':
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
                    window['pip_args'].update(' '.join(pip_args))
                pip_cmd.clear()
                pip_cmd.extend(
                    [
                        Path(sys.executable).as_posix(),
                        '-m',
                        'pip',
                        'install',
                    ] + pip_args +
                    ['-t', (output_path / f'{file_path.stem}.dist').as_posix()])
    if IS_WIN32:
        cmd.extend(['--include-module=pywin32_bootstrap'])
    for k, v in plugins.items():
        if v:
            cmd.append('--enable-plugin=%s' % k)
    file_path = Path(values['file_path'])
    cmd.append(file_path.as_posix())
    # print(subprocess.list2cmdline(cmd))
    text = 'Build:\n'
    text += subprocess.list2cmdline(cmd)
    if pip_cmd:
        text += '\nPip:\n' + subprocess.list2cmdline(pip_cmd)
    window['output'].update(text)
    cmd_list.clear()
    cmd_list.extend(cmd)


def update_plugin_list(e, items):
    for k, v in items.items():
        if str(k).startswith('_plugin_'):
            key = k[8:]
            plugins[key] = v


def print_sep(text: str):
    print('\n==================== %s ====================\n' %
          text.center(20, ' '),
          end='',
          flush=True)


def start_build(window):
    global proc
    proc = True
    window['Start'].update(disabled=True)
    window['Cancel'].update(disabled=False)
    try:
        print_sep('Build Start')
        proc = subprocess.Popen(cmd_list,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        for line in proc.stdout:
            print(line.decode('utf-8', 'replace'), end='', flush=True)
        code = proc.wait()
        if code != 0:
            raise ValueError('Bad return code: %s' % code)
        print_sep('Build Success')
        if pip_args:
            print_sep('"pip install" Start')
            print(pip_args, flush=True)
            _proc = subprocess.Popen(
                pip_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            for line in _proc.stdout:
                print(line.decode('utf-8', 'replace'), end='', flush=True)
            code = _proc.wait()
            if code != 0:
                raise ValueError('Bad return code: %s' % code)
            print_sep('"pip install" Finished')
        app_name = file_path.stem
        if values_cache['need_start_file']:
            with open(output_path / f'{app_name}.bat', 'w',
                      encoding='utf-8') as f:
                f.write(f'@echo off\ncd {app_name}.dist\nstart /B {app_name}')
        if values_cache['is_compress']:
            print_sep('Compress Start')
            src_dir = output_path / f'{file_path.stem}.dist'
            if src_dir.is_dir():
                target = output_path / f'{file_path.stem}.zip'
                with zipfile.ZipFile(target,
                                     'w',
                                     zipfile.ZIP_DEFLATED,
                                     compresslevel=9) as zf:
                    for file in src_dir.rglob('*'):
                        zf.write(file, file.relative_to(src_dir.parent))
                    if values_cache['need_start_file']:
                        zf.write(output_path / f'{app_name}.bat',
                                 f'{app_name}.bat')
                print_sep('Compress Finished')
            else:
                print(src_dir.absolute().as_posix(), 'is_dir:',
                      src_dir.is_dir())
                print_sep('Compress Skipped')
        print_sep('Mission Completed')

    except Exception:
        traceback.print_exc()
        print_sep('Error')
    proc = None
    window['Start'].update(disabled=False)
    window['Cancel'].update(disabled=True)


def main():
    sg.theme('default1')
    layout = [
        input_path('Entry Point:', 'file_path'),
        init_checkbox(),
        [
            sg.Text('--include-package:'.ljust(20)),
            sg.Input('',
                     key='--include-package',
                     tooltip='separate by Space',
                     enable_events=True),
        ],
        [
            sg.Text('--include-module:'.ljust(20)),
            sg.Input('',
                     key='--include-module',
                     tooltip='separate by Space',
                     enable_events=True)
        ],
        [
            sg.Text('Custom Args:'.ljust(20)),
            sg.Input('', key='--other-args', enable_events=True)
        ],
        input_path('Requirements:'.ljust(20), 'pip_args', sg.FilesBrowse),
        [
            sg.Text('Output Path:'),
            sg.InputText(output_path.as_posix(),
                         key='--output-dir',
                         enable_events=True),
            sg.FolderBrowse(target=(sg.ThisRow, 1), enable_events=True),
            sg.Button('View'),
            sg.Button('Remove'),
        ],
        [
            sg.Button('Start', size=(None, 10)),
            sg.Button('Cancel', disabled=True),
            sg.Button('Quit'),
            sg.Checkbox('Compress', key='is_compress', enable_events=True),
            sg.Checkbox('start.bat',
                        key='need_start_file',
                        default=True,
                        tooltip='Add start.bat as entry point.',
                        enable_events=True) if IS_WIN32 else [],
        ],
        [sg.Output(
            key='output',
            size=(80, 12),
        )],
    ]

    window = sg.Window(
        'Nuitka Toolkit',
        layout,
        # size=(800, 500),
        # font=('', 13),
        resizable=True,
        finalize=True)

    # window.maximize()

    def view_folder(event, values):
        if output_path.is_dir():
            subprocess.run(['explorer', output_path.absolute()])
        else:
            sg.popup_error(f'{output_path} is not a folder.')

    def rm_cache_dir(event, values):
        if output_path.is_dir():
            shutil.rmtree(output_path)

    actions = {
        'View': view_folder,
        'Remove': rm_cache_dir,
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
            # print(event, values, flush=True, file=old_stderr)
            if event == sg.WIN_CLOSED or event == 'Quit':
                if proc:
                    proc.kill()
                    proc.wait()
                break
            # window['output'].update(values)
            update_plugin_list(event, values)
            update_cmd(window, values)
            if event == 'Start' and not proc:
                threading.Thread(target=start_build,
                                 args=(window,),
                                 daemon=True).start()
        except BaseException:
            error = traceback.format_exc()
            break
    window.close()
    if error:
        print(error, file=old_stderr, flush=True)


if __name__ == "__main__":
    main()
