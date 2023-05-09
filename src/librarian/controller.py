import os
import time
import yaml
from librarian.exceptions import FolderCollisionException, InvalidProjectException

from librarian.service import LibraryService

LIBRARIAN_FILEPATH = "librarian.yaml"

LIBRARY_PATH_KEY = 'library-path'
WORKSPACE_PATH_KEY = 'workspace-path'
CURRENT_PROJECT_KEY = 'current-project'
CREATE_TIME_KEY = 'create-time'
MODIFY_TIME_KEY = 'modify-time'
SYNC_TARGET_KEY = 'sync-targets'

def spacing(func):
    def _func(*args, **kwargs):
        print('-----')
        func(*args, **kwargs)
        print('-----')
    return _func

def get_path(role) -> str:
    path = input(f"Enter path to {role} (enter to assign current directory): ")
    if path == "":
        path = "."

    if not os.path.exists(path):
        print(f"Invalid path to {role}: {path}. Please try again.")
        return get_path(role)
    path = os.path.realpath(path)

    confirmation = ""
    retry_times = 0
    while confirmation not in {"y", "n", "q"} and retry_times < 3:
        confirmation = input(f"Confirm path to {role}: {path} (y/n/q): ")

        if confirmation == "y":
            return path
        if confirmation == "n":
            return get_path(role)
        if confirmation == "q":
            raise KeyboardInterrupt("Quitting process.")
        print(f"Invalid input option: {confirmation}")
        retry_times += 1
    raise KeyboardInterrupt("Quitting process due to multiple invalid arguments.")

class LibrarianController:

    def __init__(self, library_path=None, workspace_path=None, sync_targets=None):
        if os.path.exists(LIBRARIAN_FILEPATH):
            with open(LIBRARIAN_FILEPATH, "r") as reader:
                data = yaml.safe_load(reader)
                self.library_path = data.get(LIBRARY_PATH_KEY)
                self.workspace_path = data.get(WORKSPACE_PATH_KEY)
                self.current_project = data.get(CURRENT_PROJECT_KEY)
                self.create_time = data.get(CREATE_TIME_KEY)
                self.modify_time = data.get(MODIFY_TIME_KEY)
                self.sync_targets = data.get(SYNC_TARGET_KEY)
            print("Retrieved Librarian data.")
        else:
            # user inputs here.
            if library_path is None:
                library_path = get_path("library")
            if workspace_path is None:
                workspace_path = get_path("workspace")
            if library_path == workspace_path:
                raise FolderCollisionException()
            print("Initialized Librarian data.")
            if sync_targets is None or len(sync_targets) == 0:
                sync_targets = ['UserData']

            self.library_path = library_path
            self.workspace_path = workspace_path
            self.current_project = None
            self.create_time = time.time()
            self.modify_time = self.create_time
            self.sync_targets = sync_targets
        
        self.service = LibraryService(self.library_path, self.workspace_path, self.sync_targets)

    @spacing
    def display_status(self):
        if not self.service.is_project(self.current_project):
            self.current_project = None
        current_project = self.current_project

        if current_project is None:
            print("There is no current project assigned.")
            return
        print(f"Current project: {current_project}")

    def update_metadata(self):
        # update librarian data
        with open(LIBRARIAN_FILEPATH, "w") as writer:
            yaml.safe_dump({
                LIBRARY_PATH_KEY: self.library_path,
                WORKSPACE_PATH_KEY: self.workspace_path,
                CURRENT_PROJECT_KEY: self.current_project,
                CREATE_TIME_KEY: self.create_time,
                MODIFY_TIME_KEY: time.time(),
                SYNC_TARGET_KEY: self.sync_targets
            }, writer)

    def _unassign_project(self):
        if self.current_project is None:
            print("No project to assign.")
            return
        current_project = self.current_project
        self.current_project = None
        print(f"Unassigned {current_project} from current project.")
        return

    def _assign_project(self, project_name):
        current_project = self.current_project
        if not self.service.is_project(project_name):
            raise InvalidProjectException(project_name)
        
        if current_project is not None:
            self._unassign_project()
        self.current_project = project_name
        print(f"Assigned {project_name} to current project")

    # actions
    def create(self, project_name):
        self.service.create_project(project_name)
        self._assign_project(project_name)

    def copy_full(self, source_project_name, destination_project_name):
        destination_project_name = self.service.copy_project(source_project_name, destination_project_name)
        if destination_project_name is None:
            return
        print(f"Copied project {source_project_name} to {destination_project_name}")

    def copy_relative(self, source_project_name, destination_project_name):
        # copy to name that is relative to the last directory.
        directory, _ = os.path.split(source_project_name)
        destination_project_name = os.path.join(directory, destination_project_name)
        self.copy_full(source_project_name, destination_project_name)
    
    def copy(self, source_project_name, destination_project_name, long=False):
        if long or destination_project_name is None:
            self.copy_full(source_project_name, destination_project_name)
        else:
            self.copy_relative(source_project_name, destination_project_name)

    def assign(self, project_name):
        self._assign_project(project_name)

    def pull(self):
        if self.current_project is not None:
            self.service.pull_project(self.current_project)
        else:
            print(f"No assigned project to pull from.")

    def push(self):
        if self.current_project is not None:
            self.service.push_project(self.current_project)
        else:
            print(f"No assigned project to push to.")

    def load_project(self, project_name):
        current_project = self.current_project
        if current_project is None or current_project == project_name:
            self._assign_project(project_name)
            self.pull()
        else:
            confirmation = input(f"\"{current_project}\" is assigned to current project. Overwrite? (y/n): ")
            if confirmation != "y":
                return
            self.current_project = None
            self.load_project(project_name)

    @spacing
    def list_projects(self, pattern):
        projects = self.service.list_projects(pattern=pattern)
        projects.sort()
        if not projects:
            print("No projects found in library.")
            return
        for project in projects:
            print(f"- {project}")

    def delete_projects(self, project_names, pattern, safe=True):
        # prioritize project names, then pattern.
        if len(project_names) == 0:
            project_names = self.service.list_projects(pattern=pattern)
            return self.delete_projects(project_names, None)

        self.service.delete_projects(project_names, safe=safe)
        if self.current_project in project_names:
            self._unassign_project()
    
    pass

