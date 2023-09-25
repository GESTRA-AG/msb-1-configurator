import os
import pathlib
import shutil

import PyInstaller.__main__ as pyinstaller

"""
This file creates an executable file for windows, linux or macosx
depending on which type of os this script is beeing run.
"""

if __name__ == "__main__":
    # constant params
    SOURCE_FILE: str = "./msb-ug6x-conf.py"
    APP_NAME: str = "MSB-UG6x-Conf.exe"
    BUILD_PATH: str = "./build"
    DIST_PATH: str = "./dist"
    SPECS_PATH: str = "./specs"

    # change path if neccessary
    workdir = pathlib.Path(
        "downlink-transmission/local-server/UG6x-Milesight-Gateway"
    )
    if not os.getcwd().endswith(str(workdir)):
        os.chdir(workdir)

    # bundle executable
    try:
        pyinstaller.run(
            [
                SOURCE_FILE,
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
        for folder in [DIST_PATH, BUILD_PATH, SPECS_PATH]:
            shutil.rmtree(folder)
    except Exception as err:
        raise err
