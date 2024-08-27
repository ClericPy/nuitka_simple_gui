# nuitka_simple_gui

> `pip install nuitka_simple_gui`
> 
> `python -m nuitka_simple_gui` or `nuitka_simple_gui`

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
2. User manual
   1. ENSURE you have installed gcc/MinGW64
      1. use the cmdline args from GUI, and type them to terminal manual at the first using.
   2. How to build
      1. Download it
         1. source code or windows executable
            1. [Source Code](https://github.com/ClericPy/nuitka_simple_gui/blob/master/nuitkaui.pyw)
               1. Auto find the Python executable path
            2. [Windows executable](https://github.com/ClericPy/nuitka_simple_gui/releases/download/Windows_executable/nuitkaui.zip)
               1. `Need to choose the Python executable path`
      2. Run it
         1. Windows friendly for now, double click it
            1. May also be compatible with other systems
      3. View it
         1. click the **View** button of Output Path line.
   3. How to use
      1. Run the app.bat for short, but it will flash a console
      2. Or you can run the app.exe in the folder app.dist
3. Documentation?
   1. GUI apps do not need docs.
4. What's More?
   1. I think about it


### Screenshot

![demo.png](https://raw.githubusercontent.com/ClericPy/nuitka_simple_gui/master/demo.png)
