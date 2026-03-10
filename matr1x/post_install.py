# This file is part of a software collection for data acquisition (matr1x).
# Copyright (C) 2006-2026 matr1x developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Perform control installation(s) and desktop integration."""

import ctypes
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
from importlib.metadata import distribution
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

import matr1x
from matr1x.gui_util import (
    SaferQSettings,
    get_install_info,
)

__all__ = [
    "post_installation",
    "remove_desktop_integration",
    "check_desktop_integration",
]

logger = logging.getLogger(__name__)

project_root = Path(__file__).parent
default_config_file = project_root / "default_matr1x.toml"
icns_path = project_root / "scripts" / "icons"
mime_path = project_root.parent
suite_settings = SaferQSettings("matr1x", "common")
start_menu_path = (
    Path.home()
    / "AppData"
    / "Roaming"
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / "matr1x"
)


def build_xdg_icon_command(
    operation: str,
    size: str = "256",
    context: str | None = None,
    theme: str | None = None,
    icon_path: str | None = None,
    application_name: str | None = None,
) -> list[str]:
    """Build xdg-icon-resource command with given parameters.

    Parameters
    ----------
    operation : str
        Either "install" or "uninstall"
    size : str, optional
        Icon size, by default "256"
    context : str, optional
        Context type (e.g., "mimetypes"), by default None
    theme : str, optional
        Theme name (e.g., "Adwaita"), by default None
    icon_path : str, optional
        Path to icon file (for install operations), by default None
    application_name : str, optional
        Application name (for MIME operations), by default None

    Returns
    -------
    list[str]
        Complete command as list of strings
    """
    cmd = ["xdg-icon-resource", operation, "--size", size]

    if context:
        cmd.extend(["--context", context])
    if theme:
        cmd.extend(["--theme", theme])
    if icon_path:
        cmd.append(icon_path)
    if application_name:
        cmd.append(application_name)

    return cmd


def xdg_install_basic_icon(icon_path: str, size: str = "256") -> list[str]:
    """Build basic icon install command."""
    return build_xdg_icon_command("install", size=size, icon_path=icon_path)


def xdg_install_mime_icon(
    icon_path: str, application_name: str, with_theme: bool = False
) -> list[str]:
    """Build MIME icon install command."""
    theme = "Adwaita" if with_theme else None
    return build_xdg_icon_command(
        "install",
        context="mimetypes",
        theme=theme,
        icon_path=icon_path,
        application_name=application_name,
    )


def xdg_uninstall_basic_icon(icon_name: str, size: str = "256") -> list[str]:
    """Build basic icon uninstall command."""
    return build_xdg_icon_command("uninstall", size=size, icon_path=icon_name)


def xdg_uninstall_mime_icon(application_name: str, with_theme: bool = False) -> list[str]:
    """Build MIME icon uninstall command."""
    theme = "Adwaita" if with_theme else None
    return build_xdg_icon_command(
        "uninstall", context="mimetypes", theme=theme, application_name=application_name
    )


def check_command(cmd: str, description: str) -> bool:
    """
    Check if a command exists on the system and exit if not found.

    Parameters
    ----------
    cmd : str
        The command to check for existence.
    description : str
        A description of the command for error messaging.

    Returns
    -------
    bool
        False if not found, True otherwise.
    """
    if shutil.which(cmd) is None:
        logger.error("%s is needed for the installation but could not be found", description)
        return False
    return True


def is_package_installed(package_name: str, pip: list) -> bool:
    """
    Check if a package is installed by querying pip.

    Parameters
    ----------
    package_name : str
        The name of the package to check.
    pip : list
        The path to python plus ["-m", "pip"] or the alternate executable.

    Returns
    -------
    bool
        True if the package is installed, False otherwise.
    """
    show_cmd = pip.copy()
    if pip[0] == "uv":
        show_cmd[2] = "show"
    else:
        show_cmd[3] = "show"
    try:
        # List installed packages and check if the package is in the output
        result = subprocess.run(
            show_cmd + [package_name],
            capture_output=True,
            check=True,
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_installed_file(file: str | Path, pkgname: str, pip: list) -> Path:
    """
    Get the full path of an installed file from a specified package.

    Parameters
    ----------
    file : str | Path
        The name or path of the file to locate.
    pkgname : str
        The name of the package containing the file.
    pip : list
        The path to python plus ["-m", "pip"] or the alternate executable.

    Returns
    -------
    Path
        The full path to the installed file.

    Raises
    ------
    SystemExit
        If the package or file cannot be found.
    """
    show_cmd = pip.copy()
    if pip[0] == "uv":
        show_cmd[2] = "show"
    else:
        show_cmd[3] = "show"
    try:
        pshow = subprocess.check_output(show_cmd + ["-f", pkgname])
    except subprocess.CalledProcessError:
        # ignore error and assume its because the requested package could not
        # be found
        pshow = b""
    pshowstr = pshow.decode()

    # get package root folder
    m = re.search("Location: (.*)[\r]?\n", pshowstr)
    if m is None:
        raise FileNotFoundError(f"Python package '{pkgname}' install location not identified")
    prefix = m.groups()[0].strip()
    # get executables relative path
    file_str = str(file)
    m = re.search(rf"\n\s+(.*){file_str}[\r]?\n", pshowstr)
    if m is None:
        raise FileNotFoundError(f"File '{file}' of package '{pkgname}' not found")
    filepath = Path(m.groups()[0]) / file
    return (Path(prefix) / filepath).resolve()


def enable_windows_virtual_terminal_processing():
    """Enable Virtual Terminal Processing for Windows 10 console."""
    if sys.platform == "win32":  # Only for Windows
        kernel32 = ctypes.windll.kernel32
        hstdout = kernel32.GetStdHandle(-11)  # Get handle to the console output
        mode = ctypes.c_ulong()

        # Get the current console mode
        kernel32.GetConsoleMode(hstdout, ctypes.byref(mode))

        # Enable the ENABLE_VIRTUAL_TERMINAL_PROCESSING flag (0x0004)
        mode.value |= 0x0004
        kernel32.SetConsoleMode(hstdout, mode)


def run_powershell(command: str) -> str:
    """
    Run a PowerShell command and return its output.

    Parameters
    ----------
    command : str
        The PowerShell command to execute.

    Returns
    -------
    str
        The output of the PowerShell command.

    Raises
    ------
    subprocess.CalledProcessError
        If the PowerShell command execution fails.
    """
    completed = subprocess.run(
        ["powershell", "-WindowStyle", "Hidden", "-Command", command],
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW
        if hasattr(subprocess, "CREATE_NO_WINDOW")
        else 0,
    )
    if completed.returncode != 0:
        logger.warning(
            "Non-zero powershell return code (%s): %s", completed.returncode, completed.stderr
        )
    return completed.stdout.strip()


def create_shortcut(
    name: str,
    exe_name: str,
    pkgname: str,
    icon_name: str,
    pip: list,
) -> None:
    """
    Create a Windows shortcut for a Matr1x application.

    Parameters
    ----------
    name : str
        The name of the shortcut to be created.
    exe_name : str
        The name of the executable file for the application.
    pkgname : str
        The name of the package containing the executable.
    icon_name : str
        The name of the icon file for the shortcut.
    pip : list
        The path to python plus ["-m", "pip"] or the alternate executable.
    """
    shortcut_path = start_menu_path / f"{name}.lnk"
    target_path = get_installed_file(exe_name, pkgname, pip)
    if is_editable("matr1x"):
        icon_path = icns_path / icon_name
    else:
        icon_path = get_installed_file(icon_name, "matr1x", pip)

    ps_command = f"""
    $WshShell = New-Object -comObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
    $Shortcut.TargetPath = "{target_path}"
    $Shortcut.IconLocation = "{icon_path}"
    $Shortcut.WorkingDirectory = $env:USERPROFILE
    $Shortcut.Save()
    """
    run_powershell(ps_command)


def check_system_specifics() -> bool:
    """
    Check dependencies (Linux) or set environment properties (Windows).

    Returns
    -------
    bool
        False if an error occured, True otherwise.
    """
    os_type = platform.system().lower()
    if "linux" in os_type or "bsd" in os_type:
        # Check for Linux/Unix dependencies
        commands_to_check = [
            ("xdg-icon-resource", "xdg-utils (xdg-icon-resource)"),
            ("xdg-mime", "xdg-utils (xdg-mime)"),
            ("desktop-file-install", "desktop-file-utils (desktop-file-install)"),
            ("update-desktop-database", "desktop-file-utils (update-desktop-database)"),
            ("update-mime-database", "shared-mime-info (update-mime-database)"),
            ("gtk-update-icon-cache", "gtk-update-icon-cache"),
        ]
        result = all(check_command(cmd, desc) for cmd, desc in commands_to_check)
        return result
    elif "windows" in os_type:
        # Set the PYTHONUTF8 environment variable for the current user
        os.environ["PYTHONUTF8"] = "1"
        os.system("setx PYTHONUTF8 1")
        return True
    return True


def create_folders() -> None:
    """Create directories specified in the configuration."""
    logger.info("Creating common folders (users and log)")
    users_folder = Path(matr1x.config["matr1x"]["users_directory"]).expanduser()
    users_folder.mkdir(parents=True, exist_ok=True)
    log_folder = Path(matr1x.config["matr1x"]["logging_directory"]).expanduser()
    log_folder.mkdir(parents=True, exist_ok=True)


def unix_integration(pip: list) -> None:
    """
    Perform Linux/Unix/BSD integration tasks for Matr1x applications.

    This function installs desktop entries, icons, and MIME types for various
    Matr1x applications on Posix compatible systems.

    Parameters
    ----------
    pip : list
        The path to python plus ["-m", "pip"] or the alternate executable.
    """
    executables = [
        (str(icns_path / "matr1x-matrix-gui.png"), "matrix-gui"),
        (str(icns_path / "matr1x-matrix-script.png"), "matrix-script"),
        (
            str(icns_path / "matr1x-sweep-generator.png"),
            "sweep-generator",
        ),
        (
            str(icns_path / "matr1x-matrix-preview.png"),
            "matrix-preview",
        ),
    ]

    for icon_path, execname in executables:
        desktop_file = execname + ".desktop"
        executable = get_installed_file(execname, "matr1x", pip)
        try:
            subprocess.run(xdg_install_basic_icon(icon_path), check=True)
            subprocess.run(
                [
                    "desktop-file-install",
                    "--mode=755",
                    f"--dir={Path.home() / '.local/share/applications'}",
                    f"{str(mime_path)}/{desktop_file}",
                    "--set-key=Exec",
                    f"--set-value={executable}",
                ],
                check=True,
            )
            logger.info("%s", desktop_file.split(".")[0])
        except subprocess.CalledProcessError:
            logger.error("Failed to install %s", desktop_file)

    # Install MIME type icons and GNOME theme icons
    try:
        # datafile
        subprocess.run(
            xdg_install_mime_icon(
                str(icns_path / "matr1x-sweep-generator.png"),
                "application-matr1x-datafile",
            ),
            check=True,
        )
        subprocess.run(
            xdg_install_mime_icon(
                str(icns_path / "matr1x-sweep-generator.png"),
                "application-matr1x-datafile",
                with_theme=True,
            ),
            check=True,
        )
        # matrix-script file
        subprocess.run(
            xdg_install_mime_icon(
                str(icns_path / "matr1x-matrix-script.png"),
                "application-matr1x-matrix",
            ),
            check=True,
        )
        subprocess.run(
            xdg_install_mime_icon(
                str(icns_path / "matr1x-matrix-script.png"),
                "application-matr1x-matrix",
                with_theme=True,
            ),
            check=True,
        )
        # sweep file
        subprocess.run(
            xdg_install_mime_icon(
                str(icns_path / "matr1x-sweep-generator.png"),
                "application-matr1x-inputfile",
            ),
            check=True,
        )
        subprocess.run(
            xdg_install_mime_icon(
                str(icns_path / "matr1x-sweep-generator.png"),
                "application-matr1x-inputfile",
                with_theme=True,
            ),
            check=True,
        )

        logger.info("Installed MIME type icons.")
    except subprocess.CalledProcessError:
        logger.error("Failed to install MIME type icons.")

    # Install MIME types and update desktop and MIME databases
    subprocess.run(
        ["xdg-mime", "install", str(mime_path / "matr1x-datafile-mime.xml")], check=True
    )
    subprocess.run(
        [
            "xdg-mime",
            "default",
            "matrix-preview.desktop",
            "application/matr1x-datafile",
        ],
        check=True,
    )
    subprocess.run(["xdg-mime", "install", str(mime_path / "matr1x-matrix-mime.xml")], check=True)
    subprocess.run(
        ["xdg-mime", "default", "matrix-script.desktop", "application/matr1x-matrix"],
        check=True,
    )
    subprocess.run(
        ["xdg-mime", "install", str(mime_path / "matr1x-inputfile-mime.xml")], check=True
    )
    subprocess.run(
        [
            "xdg-mime",
            "default",
            "sweep-generator.desktop",
            "application/matr1x-inputfile",
        ],
        check=True,
    )


def macos_integration(pyexec: Path, pip: list) -> None:
    """
    Perform MacOs integration tasks for Matr1x applications.

    This function installs desktop entries, icons, and MIME types for various
    Matr1x applications on Linux systems.

    Parameters
    ----------
    pyexec : Path
        The path to the Python executable.
    pip : list
        The path to python plus ["-m", "pip", "install"] or the alternate executable.
    """
    executables = [
        (
            str(icns_path / "matr1x-matrix-gui.png"),
            "Matrix GUI",
            "matrix-gui",
            [],
        ),
        (
            str(icns_path / "matr1x-matrix-script.png"),
            "Matrix Script",
            "matrix-script",
            ["-x", "matrix"],
        ),
        (
            str(icns_path / "matr1x-sweep-generator.png"),
            "Sweep Generator",
            "sweep-generator",
            ["-x", "sw8"],
        ),
        (
            str(icns_path / "matr1x-matrix-preview.png"),
            "Matrix Preview",
            "matrix-preview",
            ["-x", "ma6", "ma7", "ma8"],
        ),
    ]

    for icon_path, name, execname, extraopt in executables:
        executable = get_installed_file(execname, "matr1x", pip)
        # if the '-d user' option is ever changed or made variable
        # remember to change uninstall accordingly.
        try:
            cmd_list = [
                pyexec,
                "-m",
                "script2bundle",
                "-e",
                executable,
                "-d",
                "user",
                "-f",
                name,
                "-i",
                icon_path,
            ]
            cmd_list.extend(extraopt)
            original_directory = Path.cwd()
            home_directory = Path.home()
            os.chdir(home_directory)
            subprocess.run(cmd_list, check=True, capture_output=True, text=True)
            os.chdir(original_directory)
            logger.info("%s bundled successfully", name)
        except subprocess.CalledProcessError as e:
            logger.error("Failed to bundle %s for macOS: %s", name, e.stderr)


def is_editable(pkg) -> bool:
    """
    Determine if a package is editable.

    Returns
    -------
    bool
        True (editable) or not.
    """
    dist = distribution(pkg)
    data = dist.read_text("direct_url.json")
    if not data:
        return False
    return json.loads(data).get("dir_info", {}).get("editable", False)


def windows_integration(pip: list) -> None:
    """
    Perform Windows integration tasks for Matr1x applications.

    This function creates shortcuts in the Start Menu and sets up file associations
    for various Matr1x applications on Windows systems.

    Parameters
    ----------
    pip : list
        The path to python plus ["-m", "pip"] or the alternate executable.
    """
    start_menu_path.mkdir(parents=True, exist_ok=True)

    create_shortcut("Matrix GUI", "matrix-gui.exe", "matr1x", "matr1x-matrix-gui.ico", pip)
    create_shortcut(
        "Matrix Script", "matrix-script.exe", "matr1x", "matr1x-matrix-script.ico", pip
    )
    create_shortcut(
        "Sweep Generator", "sweep-generator.exe", "matr1x", "matr1x-sweep-generator.ico", pip
    )
    create_shortcut(
        "Matrix Preview", "matrix-preview.exe", "matr1x", "matr1x-matrix-preview.ico", pip
    )

    def get_icon_location(icon_name: str) -> Path:
        """
        Get the location of an icon file.

        This function determines the path of an icon file based on whether
        the installation is editable or not.

        Parameters
        ----------
        icon_name : str
            The name of the icon file.

        Returns
        -------
        Path
            The full path to the icon file.
        """
        editable = is_editable("matr1x")
        return (
            Path.cwd() / "scripts/icons" / icon_name
            if editable
            else get_installed_file(icon_name, "matr1x", pip)
        )

    icolocation_sweep = get_icon_location("matr1x-sweep-generator.ico")
    icolocation_script = get_icon_location("matr1x-matrix-script.ico")
    matrix_preview_exe = get_installed_file("matrix-preview.exe", "matr1x", pip)
    matrix_script_exe = get_installed_file("matrix-script.exe", "matr1x", pip)
    sweep_generator_exe = get_installed_file("sweep-generator.exe", "matr1x", pip)

    create_commands = f"""
    # Associate file extensions with matr1x.datafile
    # Add file association using OpenWithProgids
    New-Item -Path "HKCU:\\Software\\Classes\\.ma6" -Force;
    New-Item -Path "HKCU:\\Software\\Classes\\.ma6\\OpenWithProgids" -Force;
    New-ItemProperty -Path "HKCU:\\Software\\Classes\\.ma6\\OpenWithProgids" -Name "matr1x.datafile" -Value "" -Force;

    New-Item -Path "HKCU:\\Software\\Classes\\.ma7" -Force;
    New-Item -Path "HKCU:\\Software\\Classes\\.ma7\\OpenWithProgids" -Force;
    New-ItemProperty -Path "HKCU:\\Software\\Classes\\.ma7\\OpenWithProgids" -Name "matr1x.datafile" -Value "" -Force;

    New-Item -Path "HKCU:\\Software\\Classes\\.ma8" -Force;
    New-Item -Path "HKCU:\\Software\\Classes\\.ma8\\OpenWithProgids" -Force;
    New-ItemProperty -Path "HKCU:\\Software\\Classes\\.ma8\\OpenWithProgids" -Name "matr1x.datafile" -Value "" -Force;

    # Define the matr1x.datafile ProgID
    New-Item -Path "HKCU:\\Software\\Classes\\matr1x.datafile" -Force;
    New-ItemProperty -Path "HKCU:\\Software\\Classes\\matr1x.datafile" -Name "(Default)" -Value "Matr1x Data File" -Force;

    # Create the shell and command subkeys for matr1x.datafile
    New-Item -Path "HKCU:\\Software\\Classes\\matr1x.datafile\\shell" -Force;
    New-Item -Path "HKCU:\\Software\\Classes\\matr1x.datafile\\shell\\open" -Force;
    New-Item -Path "HKCU:\\Software\\Classes\\matr1x.datafile\\shell\\open\\command" -Force;
    New-ItemProperty -Path "HKCU:\\Software\\Classes\\matr1x.datafile\\shell\\open\\command" -Name "(Default)" -Value '\"{matrix_preview_exe}\" \"%1\"' -Force;

    # Set icon for matr1x.datafile
    New-Item -Path "HKCU:\\Software\\Classes\\matr1x.datafile\\DefaultIcon" -Force;
    New-ItemProperty -Path "HKCU:\\Software\\Classes\\matr1x.datafile\\DefaultIcon" -Name "(Default)" -Value '{icolocation_sweep}' -Force;

    # Associate file extension with matr1x.matrixfile
    New-Item -Path "HKCU:\\Software\\Classes\\.matrix" -Force;
    New-Item -Path "HKCU:\\Software\\Classes\\.matrix\\OpenWithProgids" -Force;
    New-ItemProperty -Path "HKCU:\\Software\\Classes\\.matrix\\OpenWithProgids" -Name "matr1x.matrixfile" -Value "" -Force;

    # Define the matr1x.matrixfile ProgID
    New-Item -Path "HKCU:\\Software\\Classes\\matr1x.matrixfile" -Force;
    New-ItemProperty -Path "HKCU:\\Software\\Classes\\matr1x.matrixfile" -Name "(Default)" -Value "Matr1x Script File" -Force;
    # Create the shell and command subkeys for matr1x.matrixfile
    New-Item -Path "HKCU:\\Software\\Classes\\matr1x.matrixfile\\shell" -Force;
    New-Item -Path "HKCU:\\Software\\Classes\\matr1x.matrixfile\\shell\\open" -Force;
    New-Item -Path "HKCU:\\Software\\Classes\\matr1x.matrixfile\\shell\\open\\command" -Force;
    New-ItemProperty -Path "HKCU:\\Software\\Classes\\matr1x.matrixfile\\shell\\open\\command" -Name "(Default)" -Value '\"{matrix_script_exe}\" \"%1\"' -Force;

    # Set icon for matr1x.matrixfile
    New-Item -Path "HKCU:\\Software\\Classes\\matr1x.matrixfile\\DefaultIcon" -Force;
    New-ItemProperty -Path "HKCU:\\Software\\Classes\\matr1x.matrixfile\\DefaultIcon" -Name "(Default)" -Value '{icolocation_script}' -Force;

    # Associate file extension with matr1x.inputfile
    New-Item -Path "HKCU:\\Software\\Classes\\.sw8" -Force;
    New-Item -Path "HKCU:\\Software\\Classes\\.sw8\\OpenWithProgids" -Force;
    New-ItemProperty -Path "HKCU:\\Software\\Classes\\.sw8\\OpenWithProgids" -Name "matr1x.inputfile" -Value "" -Force;

    # Define the matr1x.inputfile ProgID
    New-Item -Path "HKCU:\\Software\\Classes\\matr1x.inputfile" -Force;
    New-ItemProperty -Path "HKCU:\\Software\\Classes\\matr1x.inputfile" -Name "(Default)" -Value "Matr1x Input File" -Force;
    # Create the shell and command subkeys for matr1x.inputfile
    New-Item -Path "HKCU:\\Software\\Classes\\matr1x.inputfile\\shell" -Force;
    New-Item -Path "HKCU:\\Software\\Classes\\matr1x.inputfile\\shell\\open" -Force;
    New-Item -Path "HKCU:\\Software\\Classes\\matr1x.inputfile\\shell\\open\\command" -Force;
    New-ItemProperty -Path "HKCU:\\Software\\Classes\\matr1x.inputfile\\shell\\open\\command" -Name "(Default)" -Value '\"{sweep_generator_exe}\" \"%1\"' -Force;

    # Set icon for matr1x.inputfile
    New-Item -Path "HKCU:\\Software\\Classes\\matr1x.inputfile\\DefaultIcon" -Force;
    New-ItemProperty -Path "HKCU:\\Software\\Classes\\matr1x.inputfile\\DefaultIcon" -Name "(Default)" -Value '{icolocation_sweep}' -Force;
    """  # noqa: E501

    run_powershell(create_commands)
    logger.info("Created registry entries under HKCU:/Software/Classes")


def core_desktop_integration() -> None:
    """
    Perform desktop integration for core Matr1x applications.

    This function retrieves the paths of core Matr1x executables and calls the
    appropriate integration function based on the operating system.
    """
    matr1xpython = Path(sys.executable)
    pip = [matr1xpython, "-m", "pip", "install"]
    logger.info("Perform desktop integration")
    system_type = platform.system().lower()
    if system_type == "linux" or "bsd" in system_type:
        unix_integration(pip)
    elif system_type == "darwin":
        macos_integration(matr1xpython, pip)
    elif system_type == "windows":
        windows_integration(pip)


def control_gui_integration(pkgname: str, guilist: list[str]) -> None:
    """
    Perform desktop integration for control GUIs.

    This function installs desktop entries and icons for control GUI applications
    on Linux and macOS systems.

    Parameters
    ----------
    pkgname : str
        Package name of the control GUIs.
    guilist : List[str]
        List of control GUIs names.

    Raises
    ------
    subprocess.CalledProcessError
        If any subprocess command fails during the integration process.
    """
    matr1xpython = Path(sys.executable)
    pip = [matr1xpython, "-m", "pip", "install"]
    editable = is_editable("matr1x")
    system_type = platform.system().lower()
    for gui in guilist:
        guiname = gui.replace("_", " ").replace("-", " ")
        if system_type == "linux" or "bsd" in system_type:
            # Linux section
            try:
                icon = icns_path / "matr1x-control.png"
                control_gui_executable = get_installed_file(gui, pkgname, pip)
                subprocess.run(
                    xdg_install_basic_icon(str(icon), size="128"),
                    check=True,
                )
                desktop_file_name = Path(f"{str(mime_path)}/python.{pkgname}.{gui}.desktop")
                shutil.copy(mime_path / "matrix-controlGUI.desktop", desktop_file_name)

                subprocess.run(
                    [
                        "desktop-file-install",
                        "--mode=755",
                        "--dir={}".format(str(Path.home() / ".local/share/applications")),
                        desktop_file_name,
                        "--delete-original",
                        "--set-key=Exec",
                        f"--set-value={control_gui_executable}",
                        f"--set-name={guiname}",
                    ],
                    check=True,
                )

                logger.info("%s installed successfully", gui)

            except subprocess.CalledProcessError as e:
                logger.error("Error during GUI integration: %s", e)

        elif system_type == "darwin":
            # macOS section
            try:
                control_gui_executable = get_installed_file(gui, pkgname, pip)
                icon = icns_path / "matr1x-control.png"
                subprocess.run(
                    [
                        matr1xpython,
                        "-m",
                        "script2bundle",
                        "-e",
                        control_gui_executable,
                        "-i",
                        icon,
                        "-d",
                        "user",
                    ],
                    check=True,
                )
                logger.info("%s installed successfully", gui)
            except subprocess.CalledProcessError as e:
                logger.error("Error during GUI integration: %s", e)

        elif system_type == "windows":
            # windows section
            if editable:
                icon = icns_path / "matr1x-control.ico"
            else:
                icon = get_installed_file("matr1x-control.ico", "matr1x", pip)
            create_shortcut(guiname, gui + ".exe", pkgname, str(icon), pip)

        else:
            logger.warning("Unsupported platform: %s", platform.system())


def finalize_desktop_integration() -> None:
    """
    Finalize desktop integration by updating desktop and MIME databases on Linux.

    This function updates the desktop database, MIME database, and icon
    cache on Linux systems to ensure that newly installed applications
    and file associations are recognized by the system.

    On other platforms no action is taken.
    """
    system_type = platform.system().lower()
    if system_type == "linux" or "bsd" in system_type:
        # Update desktop and MIME databases
        subprocess.run(
            ["update-desktop-database", Path.home() / ".local/share/applications"],
            check=True,
        )
        subprocess.run(["update-mime-database", Path.home() / ".local/share/mime"], check=True)
        subprocess.run(
            [
                "gtk-update-icon-cache",
                "--ignore-theme-index",
                Path.home() / ".local/share/icons",
            ],
            check=True,
        )
        logger.info("Updated icon cache and desktop database")


def attempt_remove(filename: str | Path) -> None:
    """
    Attempt to remove a file or directory.

    This function tries to remove the specified file. If the file doesn't exist,
    it silently continues without raising an error.

    Parameters
    ----------
    filename : str or Path
        The path to the file to be removed.
    """
    path = Path(filename)
    try:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    except PermissionError:
        logger.error("Permission denied when trying to remove %s", path)


def uninstall_core_desktopintegration() -> None:
    """
    Uninstall core desktop integration for Matr1x applications.

    This function removes desktop entries, icons, and MIME types for
    various Matr1x applications on Linux, macOS, and Windows systems.

    Raises
    ------
    subprocess.CalledProcessError
        If any subprocess command fails during the uninstallation process.
    """
    system_type = platform.system().lower()

    if system_type == "linux" or "bsd" in system_type:
        try:
            # Uninstall icons and desktop files
            subprocess.run(
                xdg_uninstall_basic_icon("matr1x-matrix-gui.png"),
                check=False,
            )
            attempt_remove(Path.home() / ".local/share/applications/matrix-gui.desktop")

            # Try to remove deprecated files
            subprocess.run(
                xdg_uninstall_basic_icon("matr1x-matrix_gui.png"),
                check=False,
            )
            attempt_remove(Path.home() / ".local/share/applications/matrix_gui.desktop")

            subprocess.run(
                xdg_uninstall_basic_icon("matr1x-matrix-script.png"),
                check=False,
            )
            attempt_remove(Path.home() / ".local/share/applications/matrix-script.desktop")

            subprocess.run(
                xdg_uninstall_basic_icon("matr1x-matrix_script.png"),
                check=False,
            )
            attempt_remove(Path.home() / ".local/share/applications/matrix_script.desktop")

            subprocess.run(
                xdg_uninstall_basic_icon("matr1x-sweep-generator.png"),
                check=False,
            )
            attempt_remove(Path.home() / ".local/share/applications/sweep-generator.desktop")

            subprocess.run(
                xdg_uninstall_basic_icon("matr1x-sweep_generator.png"),
                check=False,
            )
            attempt_remove(Path.home() / ".local/share/applications/sweep_generator.desktop")

            subprocess.run(
                xdg_uninstall_basic_icon("matr1x-matrix-preview.png"),
                check=False,
            )
            attempt_remove(Path.home() / ".local/share/applications/matrix-preview.desktop")

            subprocess.run(
                xdg_uninstall_basic_icon("matr1x-matrix_preview.png"),
                check=False,
            )
            attempt_remove(Path.home() / ".local/share/applications/matrix_preview.desktop")

            # Remove deprecated application types, to be removed in 2025/26
            subprocess.run(
                xdg_uninstall_mime_icon("application-matr1x-ma7"),
                check=False,
            )
            subprocess.run(
                xdg_uninstall_mime_icon("application-matr1x-ma7", with_theme=True),
                check=False,
            )

            # Uninstall datafile/matrix-file icons and mime types
            subprocess.run(
                xdg_uninstall_mime_icon("application-matr1x-datafile"),
                check=False,
            )
            subprocess.run(
                xdg_uninstall_mime_icon("application-matr1x-datafile", with_theme=True),
                check=False,
            )
            subprocess.run(
                ["xdg-mime", "uninstall", str(mime_path / "matr1x-datafile-mime.xml")],
                check=False,
            )
            subprocess.run(
                xdg_uninstall_mime_icon("application-matr1x-matrix"),
                check=False,
            )
            subprocess.run(
                xdg_uninstall_mime_icon("application-matr1x-matrix", with_theme=True),
                check=False,
            )
            subprocess.run(
                ["xdg-mime", "uninstall", str(mime_path / "matr1x-matrix-mime.xml")],
                check=False,
            )
            subprocess.run(
                xdg_uninstall_mime_icon("application-matr1x-inputfile"),
                check=False,
            )
            subprocess.run(
                xdg_uninstall_mime_icon("application-matr1x-inputfile", with_theme=True),
                check=False,
            )
            subprocess.run(
                ["xdg-mime", "uninstall", str(mime_path / "matr1x-inputfile-mime.xml")],
                check=False,
            )

            # Update desktop and icon caches
            subprocess.run(
                [
                    "update-desktop-database",
                    str(Path.home() / ".local/share/applications"),
                ],
                check=True,
            )
            subprocess.run(
                [
                    "update-mime-database",
                    str(Path.home() / ".local/share/mime"),
                    "|",
                    "grep",
                    "-v",
                    "No such file or directory",
                ],
                check=True,
            )
            subprocess.run(
                [
                    "gtk-update-icon-cache",
                    "--ignore-theme-index",
                    str(Path.home() / ".local/share/icons"),
                ],
                check=True,
            )
            logger.info("Updated icon cache and desktop database")
        except subprocess.CalledProcessError as e:
            logger.error("Error during uninstall: %s", e)

    elif system_type == "darwin":
        # Darwin section (macOS)
        try:
            attempt_remove(Path.home() / "Applications/Matrix GUI.app")
            attempt_remove(Path.home() / "Applications/Matrix Preview.app")
            attempt_remove(Path.home() / "Applications/Matrix Script.app")
            attempt_remove(Path.home() / "Applications/Sweep Generator.app")
            logger.info("Deleted application bundles")
        except Exception as e:
            logger.error("Error during macOS uninstall: %s", e)

    elif system_type == "windows":
        # Remove existing start menu entry if it exists
        if start_menu_path.exists():
            shutil.rmtree(start_menu_path)

        # Remove file associations and registry entries
        delete_command = """
        Remove-Item -Path "HKCU:\\Software\\Classes\\.ma6" -Recurse -Force -ErrorAction SilentlyContinue;
        Remove-Item -Path "HKCU:\\Software\\Classes\\.ma7" -Recurse -Force -ErrorAction SilentlyContinue;
        Remove-Item -Path "HKCU:\\Software\\Classes\\.ma8" -Recurse -Force -ErrorAction SilentlyContinue;
        Remove-Item -Path "HKCU:\\Software\\Classes\\matr1x.datafile" -Recurse -Force -ErrorAction SilentlyContinue;
        Remove-Item -Path "HKCU:\\Software\\Classes\\.matrix" -Recurse -Force -ErrorAction SilentlyContinue;
        Remove-Item -Path "HKCU:\\Software\\Classes\\matr1x.matrixfile" -Recurse -Force -ErrorAction SilentlyContinue;
        Remove-Item -Path "HKCU:\\Software\\Classes\\.sw8" -Recurse -Force -ErrorAction SilentlyContinue;
        Remove-Item -Path "HKCU:\\Software\\Classes\\matr1x.inputfile" -Recurse -Force -ErrorAction SilentlyContinue;
        """  # noqa: E501
        run_powershell(delete_command)
        logger.info("Deleted registry entries")


def uninstall_control_gui_desktop_integration(pkgname: str, extra_guis: list[str]) -> None:
    """
    Uninstall control GUI desktop integration.

    Parameters
    ----------
    pkgname : str
        Package name of the control GUIs.
    extra_guis : List[str]
        List of control GUIs in the format 'pkgname:executable'.
    """
    system_type = platform.system().lower()

    # controlled removal of control-guis configured in the config
    for gui in extra_guis:
        if system_type == "linux" or "bsd" in system_type:
            try:
                subprocess.run(
                    xdg_uninstall_basic_icon("matr1x-control.png"),
                    check=True,
                )
                attempt_remove(
                    Path.home() / ".local/share/applications" / f"{gui}.desktop"
                )  # remove in 2025/26
                attempt_remove(
                    Path.home() / ".local/share/applications" / f"python.{pkgname}.{gui}.desktop"
                )
            except Exception as e:
                logger.error("Error removing %s: %s", gui, e)
        elif system_type == "darwin":
            try:
                attempt_remove(Path.home() / "Applications" / f"{gui}.app")
                logger.info("Deleted %s", gui)
            except Exception as e:
                logger.error("Error removing %s: %s", gui, e)
        elif system_type == "windows":
            pass

    # removal of remaining files
    if system_type == "linux" or "bsd" in system_type:
        # Find and remove files following the pattern
        desktop_files = Path.home().glob(f".local/share/applications/python.{pkgname}.*.desktop")
        for file in desktop_files:
            try:
                file.unlink()
                logger.info("Removed desktop file: %s", file)
            except Exception as e:
                logger.error("Error removing %s: %s", file, e)


def remove_desktop_integration():
    """Remove the desktop integration."""
    logger.info("Perform removal of old files")
    suite_settings.setValue("di_version", "0")
    uninstall_core_desktopintegration()
    for pkg_name in matr1x.config:
        if "install" in matr1x.config[pkg_name]:
            guis = matr1x.config[pkg_name]["install"].get("controlguis", [])
            uninstall_control_gui_desktop_integration(pkg_name, guis)


def check_desktop_integration():
    """Check the desktop integration."""
    version, _, _, _ = get_install_info(matr1x)
    last_version = suite_settings.safer_value("di_version", "0", type=str)
    if version != last_version:
        logger.info("Performing automatic desktop integration.")
        post_installation()
    else:
        logger.info("Skipping automatic desktop integration.")


def post_installation():
    """
    Run post-installation tasks.

    Installs the control GUIs and performs the desktop integration.

    Returns
    -------
    bool
        Post installation successful (True) or not (False).
    """
    enable_windows_virtual_terminal_processing()
    logger.info("Check and/or set platform specifics")
    if not check_system_specifics():
        QMessageBox.warning(
            None,
            "Warning",
            "PI001: Not all platform specifics found! Please refer to the documentation.",
            QMessageBox.StandardButton.Ok,
        )
        return
    remove_desktop_integration()
    if matr1x.config["matr1x"]["install"]["create_directories"]:
        create_folders()
    if matr1x.config["matr1x"]["install"]["desktopintegration"]:
        core_desktop_integration()
        # desktop integration for control guis
        for pkg_name in matr1x.config:
            if "install" in matr1x.config[pkg_name]:
                guis = matr1x.config[pkg_name]["install"].get("controlguis", [])
                control_gui_integration(pkg_name, guis)
        finalize_desktop_integration()
    version, _, _, _ = get_install_info(matr1x)
    suite_settings.setValue("di_version", version)
    logger.info("Post-installation succeeded")
