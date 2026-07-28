import os
import shutil
from pathlib import Path

from core.tool import Tool
from core.tool_schema import ActionSchema, PERMISSION_CONFIRM


class FileTool(Tool):
    name = "files"

    description = (
        "Create, open, search, rename, copy, move, and delete files "
        "and folders."
    )
    actions = {
        "open_folder": ActionSchema(
            description="Open a folder.",
            required_arguments=("folder",),
            example={"folder": "Documents"},
        ),
        "create_folder": ActionSchema(
            description="Create a folder at a chosen location.",
            required_arguments=("folder_name", "location"),
            example={
                "folder_name": "Project Ideas",
                "location": "Documents",
            },
        ),
        "create_file": ActionSchema(
            description="Create a file, optionally with text content.",
            required_arguments=("file_name", "location"),
            optional_arguments=("content",),
            example={
                "file_name": "notes.txt",
                "location": "Desktop",
                "content": "Optional text",
            },
        ),
        "search_files": ActionSchema(
            description="Search common folders for a file or folder.",
            required_arguments=("query",),
            example={"query": "project notes"},
        ),
        "open_file": ActionSchema(
            description="Find and open a file.",
            required_arguments=("query",),
            example={"query": "notes.txt"},
        ),
        "rename_file": ActionSchema(
            description="Rename a file.",
            required_arguments=("query", "new_name"),
            permission=PERMISSION_CONFIRM,
            confirmation_message="Rename this file?",
            example={
                "query": "old-name.txt",
                "new_name": "new-name.txt",
            },
        ),
        "copy_file": ActionSchema(
            description="Copy a file to another folder.",
            required_arguments=("query", "destination"),
            example={
                "query": "notes.txt",
                "destination": "Documents",
            },
        ),
        "move_file": ActionSchema(
            description="Move a file to another folder.",
            required_arguments=("query", "destination"),
            permission=PERMISSION_CONFIRM,
            confirmation_message="Move this file?",
            example={
                "query": "notes.txt",
                "destination": "Documents",
            },
        ),
        "delete_file": ActionSchema(
            description="Permanently delete a file.",
            required_arguments=("query",),
            permission=PERMISSION_CONFIRM,
            confirmation_message="Delete this file permanently?",
            example={"query": "old-notes.txt"},
        ),
        "delete_folder": ActionSchema(
            description="Permanently delete an empty folder.",
            required_arguments=("query",),
            permission=PERMISSION_CONFIRM,
            confirmation_message="Delete this empty folder permanently?",
            example={"query": "Old Project"},
        ),
    }

    def __init__(self):
        self.home = Path.home()

        self.common_folders = {
            "desktop": self.home / "Desktop",
            "downloads": self.home / "Downloads",
            "documents": self.home / "Documents",
            "pictures": self.home / "Pictures",
            "music": self.home / "Music",
            "videos": self.home / "Videos",
        }

        self.search_locations = [
            self.home / "Desktop",
            self.home / "Downloads",
            self.home / "Documents",
            self.home / "Pictures",
        ]

    def execute(self, args=None):
        if not args:
            return "Please provide a file action."

        action = str(args.get("action", "")).strip().lower()

        if action == "open_folder":
            return self.open_folder(
                args.get("folder"),
            )

        if action == "create_folder":
            return self.create_folder(
                args.get("folder_name"),
                args.get("location", "desktop"),
            )

        if action == "create_file":
            return self.create_file(
                args.get("file_name"),
                args.get("location", "desktop"),
                args.get("content", ""),
            )

        if action == "search_files":
            return self.search_files(
                args.get("query"),
            )

        if action == "open_file":
            return self.open_file(
                args.get("query"),
            )

        if action == "rename_file":
            return self.rename_file(
                args.get("query"),
                args.get("new_name"),
            )

        if action == "copy_file":
            return self.copy_file(
                args.get("query"),
                args.get("destination"),
            )

        if action == "move_file":
            return self.move_file(
                args.get("query"),
                args.get("destination"),
            )

        if action == "delete_file":
            return self.delete_file(
                args.get("query"),
            )

        if action == "delete_folder":
            return self.delete_folder(
                args.get("query"),
            )

        return f"Unknown file action: {action}"

    def get_folder_path(self, folder_name):
        if not folder_name:
            return None

        folder_name = str(folder_name).strip()
        normalized_name = folder_name.lower()

        if normalized_name in self.common_folders:
            return self.common_folders[normalized_name]

        possible_path = Path(folder_name).expanduser()

        if possible_path.exists() and possible_path.is_dir():
            return possible_path

        return None

    def resolve_location(self, location):
        if not location:
            location = "desktop"

        return self.get_folder_path(location)

    def open_folder(self, folder_name):
        folder_path = self.get_folder_path(folder_name)

        if folder_path is None:
            return f"Folder '{folder_name}' was not found."

        if not folder_path.is_dir():
            return f"'{folder_name}' is not a folder."

        try:
            os.startfile(str(folder_path))
            return f"Opened the {folder_name} folder."

        except OSError as error:
            return f"Could not open the folder: {error}"

    def create_folder(
        self,
        folder_name,
        location="desktop",
    ):
        if not folder_name:
            return "Please provide a folder name."

        location_path = self.resolve_location(location)

        if location_path is None:
            return f"Location '{location}' was not found."

        folder_name = str(folder_name).strip()

        if not folder_name:
            return "Please provide a valid folder name."

        new_folder = location_path / folder_name

        try:
            new_folder.mkdir(
                parents=True,
                exist_ok=False,
            )

            return (
                f"Created folder '{folder_name}' "
                f"in {location}."
            )

        except FileExistsError:
            return (
                f"A file or folder named "
                f"'{folder_name}' already exists."
            )

        except PermissionError:
            return (
                "Permission denied while creating "
                "the folder."
            )

        except OSError as error:
            return f"Could not create the folder: {error}"

    def create_file(
        self,
        file_name,
        location="desktop",
        content="",
    ):
        if not file_name:
            return "Please provide a file name."

        location_path = self.resolve_location(location)

        if location_path is None:
            return f"Location '{location}' was not found."

        file_name = str(file_name).strip()

        if not file_name:
            return "Please provide a valid file name."

        file_path = location_path / file_name

        if file_path.exists():
            return (
                f"A file or folder named "
                f"'{file_name}' already exists."
            )

        if content is None:
            content = ""

        if not isinstance(content, str):
            content = str(content)

        try:
            file_path.write_text(
                content,
                encoding="utf-8",
            )

            return (
                f"Created file '{file_name}' "
                f"in {location}."
            )

        except PermissionError:
            return (
                "Permission denied while creating "
                "the file."
            )

        except OSError as error:
            return f"Could not create the file: {error}"

    def find_matches(self, query):
        if not query:
            return []

        query_text = str(query).strip()

        if not query_text:
            return []

        direct_path = Path(query_text).expanduser()

        if direct_path.exists():
            return [direct_path]

        normalized_query = query_text.lower()
        matches = []

        for location in self.search_locations:
            if not location.exists():
                continue

            try:
                for path in location.rglob("*"):
                    if normalized_query in path.name.lower():
                        matches.append(path)

                        if len(matches) >= 20:
                            return matches

            except PermissionError:
                continue

            except OSError:
                continue

        return matches

    def search_files(self, query):
        if not query:
            return "Please provide a file name to search for."

        matches = self.find_matches(query)

        if not matches:
            return (
                f"No files or folders matching "
                f"'{query}' were found."
            )

        result_lines = [
            f"Found {len(matches)} match(es):"
        ]

        for index, path in enumerate(
            matches,
            start=1,
        ):
            item_type = (
                "Folder"
                if path.is_dir()
                else "File"
            )

            result_lines.append(
                f"{index}. [{item_type}] {path}"
            )

        return "\n".join(result_lines)

    def find_first_file(self, query):
        matches = self.find_matches(query)

        for match in matches:
            if match.is_file():
                return match

        return None

    def find_first_folder(self, query):
        matches = self.find_matches(query)

        for match in matches:
            if match.is_dir():
                return match

        return None

    def open_file(self, query):
        if not query:
            return "Please provide a file name."

        file_path = self.find_first_file(query)

        if file_path is None:
            return (
                f"No file matching '{query}' was found."
            )

        try:
            os.startfile(str(file_path))

            return f"Opened '{file_path.name}'."

        except OSError as error:
            return f"Could not open the file: {error}"

    def rename_file(
        self,
        query,
        new_name,
    ):
        if not query or not new_name:
            return (
                "Please provide the current file name "
                "and the new file name."
            )

        file_path = self.find_first_file(query)

        if file_path is None:
            return (
                f"No file matching '{query}' was found."
            )

        new_name = str(new_name).strip()

        if not new_name:
            return "Please provide a valid new file name."

        if not Path(new_name).suffix:
            new_name += file_path.suffix

        new_path = file_path.with_name(new_name)

        if new_path.exists():
            return (
                f"A file named '{new_path.name}' "
                f"already exists."
            )

        try:
            old_name = file_path.name
            file_path.rename(new_path)

            return (
                f"Renamed '{old_name}' "
                f"to '{new_path.name}'."
            )

        except PermissionError:
            return (
                "Permission denied while renaming "
                "the file."
            )

        except OSError as error:
            return f"Could not rename the file: {error}"

    def copy_file(
        self,
        query,
        destination,
    ):
        if not query or not destination:
            return (
                "Please provide a file name "
                "and destination."
            )

        file_path = self.find_first_file(query)
        destination_path = self.get_folder_path(destination)

        if file_path is None:
            return (
                f"No file matching '{query}' was found."
            )

        if destination_path is None:
            return (
                f"Destination '{destination}' "
                f"was not found."
            )

        new_path = destination_path / file_path.name

        if new_path.exists():
            return (
                f"'{file_path.name}' already exists "
                f"in {destination}."
            )

        try:
            shutil.copy2(
                str(file_path),
                str(new_path),
            )

            return (
                f"Copied '{file_path.name}' "
                f"to the {destination} folder."
            )

        except PermissionError:
            return (
                "Permission denied while copying "
                "the file."
            )

        except OSError as error:
            return f"Could not copy the file: {error}"

    def move_file(
        self,
        query,
        destination,
    ):
        if not query or not destination:
            return (
                "Please provide a file name "
                "and destination."
            )

        file_path = self.find_first_file(query)
        destination_path = self.get_folder_path(destination)

        if file_path is None:
            return (
                f"No file matching '{query}' was found."
            )

        if destination_path is None:
            return (
                f"Destination '{destination}' "
                f"was not found."
            )

        new_path = destination_path / file_path.name

        if new_path.exists():
            return (
                f"'{file_path.name}' already exists "
                f"in {destination}."
            )

        try:
            shutil.move(
                str(file_path),
                str(new_path),
            )

            return (
                f"Moved '{file_path.name}' "
                f"to the {destination} folder."
            )

        except PermissionError:
            return (
                "Permission denied while moving "
                "the file."
            )

        except OSError as error:
            return f"Could not move the file: {error}"

    def delete_file(self, query):
        if not query:
            return "Please provide a file name."

        file_path = self.find_first_file(query)

        if file_path is None:
            return (
                f"No file matching '{query}' was found."
            )

        try:
            file_name = file_path.name
            file_path.unlink()

            return f"Deleted file '{file_name}'."

        except PermissionError:
            return (
                "Permission denied while deleting "
                "the file."
            )

        except OSError as error:
            return f"Could not delete the file: {error}"

    def delete_folder(self, query):
        if not query:
            return "Please provide a folder name."

        folder_path = self.find_first_folder(query)

        if folder_path is None:
            return (
                f"No folder matching '{query}' was found."
            )

        if folder_path in self.common_folders.values():
            return (
                "MV.AI will not delete protected "
                "system folders."
            )

        try:
            folder_name = folder_path.name

            folder_path.rmdir()

            return f"Deleted empty folder '{folder_name}'."

        except OSError:
            return (
                f"Folder '{folder_path.name}' is not empty. "
                "The MVP only deletes empty folders."
            )

        except PermissionError:
            return (
                "Permission denied while deleting "
                "the folder."
            )