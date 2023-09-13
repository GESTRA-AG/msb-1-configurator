import os, sys
import shutil

import PyInstaller.__main__ as pyinstaller

"""
This file creates an executable file for windows, linux or macosx
depending on which type of os this script is beeing run.
"""

if __name__ == "__main__":
    # constant params
    APP_NAME: str = "MSB-UG6x-Conf.exe"
    BUILD_PATH: str = "./build"
    DIST_PATH: str = "./dist"
    SPECS_PATH: str = "./specs"

    # change path if neccessary
    try:
        cwd = os.getcwd()
        if not cwd.endswith(APP_NAME):
            path = os.path.abspath(os.path.join(cwd, APP_NAME))
            if os.path.exists(path) and os.path.isdir(path):
                os.chdir(path)
    except Exception as err:
        raise err

    # bundle executable
    try:
        pyinstaller.run(
            [
                "./msb-ug6x-conf.py",
                "--name",
                APP_NAME,
                "--distpath",
                DIST_PATH,
                "--workpath",
                BUILD_PATH,
                "--specpath",
                SPECS_PATH,
                "--onefile",
                "--noconsole",
                "--clean",
                "--noconfirm",
            ]
        )
    except Exception as err:
        raise err

    # move executable
    try:
        dist = os.listdir(DIST_PATH)
        for exe in dist:
            if exe.startswith(APP_NAME):
                shutil.copy2(src=f"{DIST_PATH}/{exe}", dst=f"./{exe}")
    except Exception as err:
        raise err
