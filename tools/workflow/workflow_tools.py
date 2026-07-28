import os
import shutil
import subprocess
import webbrowser
from pathlib import Path

from core.tool import Tool


class WorkflowTool(Tool):
    """
    Runs predefined MV.AI workflows.

    Current workflow:
    - Spark Code Setup
    """

    name = "workflow"

    description = (
        "Runs predefined multi-app workflows such as "
        "Spark Code Setup."
    )

    def __init__(self):
        self.home = Path.home()

        self.search_locations = [
            self.home / "Desktop",
            self.home / "Documents",
            self.home / "Downloads",
        ]

        self.default_project_location = (
            self.home
            / "Desktop"
        )

    def execute(self, args=None):
        if not args:
            return "Please provide a workflow action."

        action = str(
            args.get("action", "")
        ).strip().lower()

        if action == "spark_code_setup":
            return self.spark_code_setup(
                project_name=args.get("project_name"),
            )

        return f"Unknown workflow action: {action}"

    def spark_code_setup(
        self,
        project_name=None,
    ):
        """
        Open the coding environment.

        When a project name is supplied:
        - Find the project folder.
        - Create it when missing.
        - Open it in VS Code.
        - Open it in File Explorer.

        Always:
        - Open ChatGPT in the browser.
        """

        results = []

        project_path = None
        project_created = False

        if project_name:
            project_name = str(
                project_name
            ).strip()

            if project_name:
                project_path = (
                    self.find_project_folder(
                        project_name
                    )
                )

                if project_path is None:
                    project_path = (
                        self.create_project_folder(
                            project_name
                        )
                    )

                    if project_path is not None:
                        project_created = True

        if project_path is not None:
            vscode_result = (
                self.open_vscode_project(
                    project_path
                )
            )

            explorer_result = (
                self.open_project_in_explorer(
                    project_path
                )
            )

            results.append(vscode_result)
            results.append(explorer_result)

        else:
            results.append(
                self.open_vscode()
            )

            results.append(
                self.open_file_explorer()
            )

        results.append(
            self.open_chatgpt()
        )

        if project_created and project_path:
            results.insert(
                0,
                (
                    f"Created project folder "
                    f"'{project_path.name}' "
                    f"at {project_path}."
                ),
            )

        return "\n".join(results)

    def find_project_folder(
        self,
        project_name,
    ):
        """
        Search common user folders for a matching project.
        """

        normalized_name = (
            project_name
            .lower()
            .replace("_", " ")
            .replace("-", " ")
            .strip()
        )

        direct_path = Path(
            project_name
        ).expanduser()

        if (
            direct_path.exists()
            and direct_path.is_dir()
        ):
            return direct_path.resolve()

        best_match = None

        for location in self.search_locations:
            if not location.exists():
                continue

            try:
                for path in location.rglob("*"):
                    if not path.is_dir():
                        continue

                    normalized_folder = (
                        path.name
                        .lower()
                        .replace("_", " ")
                        .replace("-", " ")
                        .strip()
                    )

                    if normalized_folder == normalized_name:
                        return path.resolve()

                    if (
                        normalized_name
                        in normalized_folder
                        and best_match is None
                    ):
                        best_match = path.resolve()

            except PermissionError:
                continue

            except OSError:
                continue

        return best_match

    def create_project_folder(
        self,
        project_name,
    ):
        """
        Create a missing project folder on the Desktop.
        """

        safe_name = self.clean_project_name(
            project_name
        )

        if not safe_name:
            return None

        project_path = (
            self.default_project_location
            / safe_name
        )

        try:
            project_path.mkdir(
                parents=True,
                exist_ok=True,
            )

            return project_path.resolve()

        except OSError:
            return None

    @staticmethod
    def clean_project_name(
        project_name,
    ):
        """
        Remove characters Windows does not allow in names.
        """

        invalid_characters = (
            '<>:"/\\|?*'
        )

        cleaned_name = str(
            project_name
        ).strip()

        for character in invalid_characters:
            cleaned_name = (
                cleaned_name.replace(
                    character,
                    "",
                )
            )

        return cleaned_name.strip()

    def open_vscode_project(
        self,
        project_path,
    ):
        """
        Open a project folder directly in VS Code.
        """

        code_command = shutil.which(
            "code"
        )

        if code_command:
            try:
                subprocess.Popen(
                    [
                        code_command,
                        str(project_path),
                    ],
                    shell=False,
                )

                return (
                    f"Opened '{project_path.name}' "
                    f"in VS Code."
                )

            except OSError as error:
                return (
                    "Could not open the project "
                    f"in VS Code: {error}"
                )

        possible_paths = [
            (
                self.home
                / "AppData"
                / "Local"
                / "Programs"
                / "Microsoft VS Code"
                / "Code.exe"
            ),
            Path(
                "C:/Program Files/"
                "Microsoft VS Code/"
                "Code.exe"
            ),
        ]

        for vscode_path in possible_paths:
            if not vscode_path.exists():
                continue

            try:
                subprocess.Popen(
                    [
                        str(vscode_path),
                        str(project_path),
                    ],
                    shell=False,
                )

                return (
                    f"Opened '{project_path.name}' "
                    f"in VS Code."
                )

            except OSError as error:
                return (
                    "Could not open the project "
                    f"in VS Code: {error}"
                )

        return (
            "VS Code does not appear "
            "to be installed."
        )

    def open_vscode(self):
        """
        Open VS Code without a project.
        """

        code_command = shutil.which(
            "code"
        )

        if code_command:
            try:
                subprocess.Popen(
                    [code_command],
                    shell=False,
                )

                return "Opened VS Code."

            except OSError as error:
                return (
                    f"Could not open VS Code: {error}"
                )

        possible_paths = [
            (
                self.home
                / "AppData"
                / "Local"
                / "Programs"
                / "Microsoft VS Code"
                / "Code.exe"
            ),
            Path(
                "C:/Program Files/"
                "Microsoft VS Code/"
                "Code.exe"
            ),
        ]

        for vscode_path in possible_paths:
            if not vscode_path.exists():
                continue

            try:
                os.startfile(
                    str(vscode_path)
                )

                return "Opened VS Code."

            except OSError as error:
                return (
                    f"Could not open VS Code: {error}"
                )

        return (
            "VS Code does not appear "
            "to be installed."
        )

    @staticmethod
    def open_project_in_explorer(
        project_path,
    ):
        """
        Open the project folder in Windows Explorer.
        """

        try:
            os.startfile(
                str(project_path)
            )

            return (
                f"Opened '{project_path.name}' "
                "in File Explorer."
            )

        except OSError as error:
            return (
                "Could not open the project "
                f"in File Explorer: {error}"
            )

    @staticmethod
    def open_file_explorer():
        """
        Open Windows File Explorer.
        """

        try:
            subprocess.Popen(
                ["explorer.exe"],
                shell=False,
            )

            return "Opened File Explorer."

        except OSError as error:
            return (
                f"Could not open File Explorer: {error}"
            )

    @staticmethod
    def open_chatgpt():
        """
        Open ChatGPT in the default browser.
        """

        try:
            opened = webbrowser.open(
                "https://chatgpt.com",
                new=2,
            )

            if opened:
                return "Opened ChatGPT."

            return (
                "The browser did not confirm "
                "that ChatGPT was opened."
            )

        except Exception as error:
            return (
                f"Could not open ChatGPT: {error}"
            )