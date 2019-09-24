import datetime
import os
from typing import Callable, NoReturn

import requests

from utils import partition


def check_token(fn: Callable):
    def wrapper(self, *args, **kwargs):
        if self.token is None or self.token_expiration < datetime.datetime.utcnow():
            self.set_token()
        return fn(self, *args, **kwargs)

    return wrapper


class PowerBIAPIClient:
    def __init__(self, tenant_id, client_id, client_secret):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://api.powerbi.com/v1.0/myorg/"
        self.url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        self.token = None
        self.token_expiration = None
        self._workspaces = None
        self.headers = None

    def set_token(self):
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "scope": "https://analysis.windows.net/powerbi/api/.default",
            "client_secret": self.client_secret,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = requests.post(self.url, data=payload, headers=headers)

        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.token_expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
            self.headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Bearer {self.token}",
            }
        else:
            print(f"Expected response code 200 when trying to set token, got {response.status_code}: {response.text}.")

    @property
    def workspaces(self):
        return self._workspaces or self.get_workspaces()

    @check_token
    def get_workspaces(self):
        url = self.base_url + "groups"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            self._workspaces = response.json()["value"]
            return self._workspaces
        self.force_raise_http_error(response)

    def find_workspace_id_by_name(self, name):
        if self._workspaces is not None:
            for item in self._workspaces:
                if item["name"] == name:
                    return item["id"]

    @check_token
    def create_workspace(self, name):
        # Check if workspace exists already:
        url = self.base_url + f"groups?$filter=contains(name,'{name}')"
        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            print(
                "Expected response code 200 when checking if the workspace already exists, "
                f"got {response.status_code}: {response.text}."
            )
            self.force_raise_http_error(response)

        if response.json()["@odata.count"] > 0:
            print("Workspace already exists; no changes made!")
            return

        # Workspace does not exist, lets create it:
        print(f"Trying to create a workspace with name: {name}...")
        url = self.base_url + "groups?workspaceV2=true"
        response = requests.post(url, data={"name": name}, headers=self.headers)

        if response.status_code == 200:
            print("Workspace created successfully!")
            self.get_workspaces()  # Update internal state
            return
        else:
            print(
                "Expected response code 200 when trying to create the new workspace, "
                f"got {response.status_code}: {response.text}."
            )
            self.force_raise_http_error(response)

    @check_token
    def add_users_to_workspace(self, workspace_name, users):
        self.get_workspaces()
        workspace_id = self.find_workspace_id_by_name(workspace_name)

        if workspace_id is None:
            raise RuntimeError(f"No workspace named '{workspace_name}', thus adding users to it failed!")

        # Workspace exists, lets add users:
        url = self.base_url + f"groups/{workspace_id}/users"
        response = requests.post(url, data=users, headers=self.headers)

        if response.status_code == 200:
            print(f"Added users to workspace '{workspace_name}'")
            return
        else:
            print(
                f"Expected response code 200 when trying to add users to workspace '{workspace_name}', "
                f"got {response.status_code}: {response.text}."
            )
            self.force_raise_http_error(response)

    @check_token
    def delete_workspace(self, workspace_name):
        workspace_id = self.find_workspace_id_by_name(workspace_name)

        if workspace_id is None:
            raise RuntimeError(f"No workspace named '{workspace_name}', thus adding users to it failed!")

        url = self.base_url + "groups/{workspace_id}"
        response = requests.delete(url, headers=self.headers)

        if response.status_code == 200:
            print("Workspace deleted successfully!")
        else:
            print("Workspace deletion failed:")
            self.force_raise_http_error(response)

    @check_token
    def get_datasets_in_workspace(self, workspace_id):
        datasets_url = self.base_url + f"groups/{workspace_id}/datasets"
        response = requests.get(datasets_url, headers=self.headers)
        response.raise_for_status()
        if response.status_code == 200:
            return response.json()["value"]

    def find_dataset_id_by_name(self, datasets, name):
        for item in datasets:
            if item["name"] == name:
                return item["id"]

    @check_token
    def refresh_dataset_by_id(self, workspace_id, dataset_id):
        url = self.base_url + f"groups/{workspace_id}/datasets/{dataset_id}/refreshes"
        payload = "notifyOption=NoNotification"
        response = requests.post(url, data=payload, headers=self.headers)

        if response.status_code == 202:
            print(f"Dataset with id {dataset_id} (and workspace id {workspace_id}) was updated!")
        else:
            print("Expected 202 response code, got {response.status_code}: {response.text}")
            self.force_raise_http_error(response)

    @check_token
    def create_push_dataset(self, workspace_id, retention_policy):
        url = self.base_url + f"groups/{workspace_id}/datasets?defaultRetentionPolicy={retention_policy}"
        payload = "notifyOption=NoNotification"
        response = requests.post(url, data=payload, headers=self.headers)

        if response.status_code == 202:
            print(
                f"Create push dataset successful using workspace_id: {workspace_id} and "
                f"retention_policy: {retention_policy}"
            )
        else:
            print("Expected 202 response code, got {response.status_code}: {response.text}")
            self.force_raise_http_error(response)

    @check_token
    def create_dataset(self, workspace_id, schema, retention_policy):
        url = self.base_url + f"groups/{workspace_id}/datasets?defaultRetentionPolicy={retention_policy}"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.post(url, json=schema, headers=headers)

        if response.status_code in [201, 202]:
            print(
                f"Create dataset successful using workspace_id: {workspace_id}, schema: {schema} "
                f"and retention_policy: {retention_policy}"
            )
        else:
            print(f"Expected response code 201 or 202, got {response.status_code}: {response.text}")
            self.force_raise_http_error(response)

    @check_token
    def delete_dataset(self, workspace_id, dataset_id):
        url = self.base_url + f"groups/{workspace_id}/datasets/{dataset_id}"
        response = requests.delete(url, headers=self.headers)
        if response.status_code == 200:
            print("Dataset with id: {dataset_id} in workspace with id: {workspace_id} deleted successfully!")
        else:
            print(f"Expected response code 200, got {response.status_code}: {response.text}")
            self.force_raise_http_error(response)

    @check_token
    def post_rows(self, workspace_id, dataset_id, table_name, data, chunk_size: int = 10000):
        url = self.base_url + f"groups/{workspace_id}/datasets/{dataset_id}/tables/{table_name}/rows"
        headers = {"Authorization": f"Bearer {self.token}"}

        chunked_data = partition(data, n=chunk_size)
        tot_chunks = len(chunked_data)

        for i, row_chunk in enumerate(chunked_data, 1):
            response = requests.post(url, json={"rows": row_chunk}, headers=headers)
            if response.status_code == 200:
                print(f"Chunk [i/{tot_chunks}] inserted successfully! Size: {len(row_chunk)} rows")
            else:
                print(
                    "Row insertion failed! Expected response code 200, got " f"{response.status_code}: {response.text}"
                )
                self.force_raise_http_error(response)

    @check_token
    def update_table_schema(self, workspace_id, dataset_id, table_name, schema):
        url = self.base_url + f"groups/{workspace_id}/datasets/{dataset_id}/tables/{table_name}"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.put(url, json=schema, headers=headers)
        # TODO(scottmelhop): Use/check/raise depending on status code?
        print(f"Update table schema returned status code {response.status_code}: {response.text}")

    @check_token
    def get_tables(self, workspace_id, dataset_id):
        url = self.base_url + "groups/{workspace_id}/datasets/{dataset_id}/tables"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            return response.json()

    @check_token
    def truncate_table(self, workspace_id, dataset_id, table_name):
        url = self.base_url + "groups/{workspace_id}/datasets/{dataset_id}/tables/{table_name}/rows"
        response = requests.delete(url, headers=self.headers)

        if response.status_code == 200:
            print("Table truncation successful!")
        else:
            print(
                "Table truncation failed! Expected response code 200, got " f"{response.status_code}: {response.text}"
            )
            self.force_raise_http_error(response)

    @check_token
    def get_reports_in_workspace(self, workspace_name):
        workspace_id = self.find_workspace_id_by_name(workspace_name)

        if workspace_id is None:
            raise RuntimeError(f"Fetching reports failed as no workspace is named '{workspace_name}'!")

        url = self.base_url + f"groups/{workspace_id}/reports"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            return response.json()["value"]

    def find_report_id_by_name(self, reports, name):
        for item in reports:
            if item["name"] == name:
                return item["id"]

    @check_token
    def delete_report(self, workspace_name, report_name):
        workspace_id = self.find_workspace_id_by_name(workspace_name)

        if workspace_id is None:
            raise RuntimeError(f"Deleting report failed as no workspace is named '{workspace_name}'!")

        reports = self.get_reports_in_workspace(workspace_name)
        report_id = self.find_report_id_by_name(reports, report_name)

        if report_id is None:
            raise RuntimeError(
                f"Deleting report failed as no report is named '{report_name}' in workspace '{workspace_name}'!"
            )

        url = self.base_url + f"groups/{workspace_id}/reports/{report_id}"
        response = requests.delete(url, headers=self.headers)

        if response.status_code == 200:
            print("Report named '{report_name}' in workspace '{workspace_name}' deleted successfully!")
        else:
            print(f"Report deletion failed! Expected response code 200, got {response.status_code}: {response.text}")
            self.force_raise_http_error(response)

    @check_token
    def import_file_into_workspace(self, workspace_name, skip_report, file_path, display_name):
        workspace_id = self.find_workspace_id_by_name(workspace_name)

        if workspace_id is None:
            raise RuntimeError(f"Importing file into workspace failed as workspace '{workspace_name}' does not exists!")

        name_conflict = "CreateOrOverwrite"
        url = (
            self.base_url
            + f"groups/{workspace_id}/imports?datasetDisplayName={display_name}&nameConflict="
            + f"{name_conflict}&skipReport={skip_report}"
        )

        headers = {"Content-Type": "multipart/form-data", "Authorization": "Bearer " + self.token}

        if not os.path.isfile(file_path):
            raise FileNotFoundError(2, f"No such file or directory: '{file_path}'")

        with open(file_path, "rb") as f:
            response = requests.post(url, headers=headers, files={"filename": f})

        if response.status_code == 202:
            print(response.json())
            import_id = response.json()["id"]
            print(f"File uploading with id: {import_id}")
            return
        else:
            return False

            # This code doesnt work yet, keeps returning 403
            # get_import_url = self.base_url + f"imports/{import_id}"
            # print(get_import_url)
            #
            # while True:
            #     response = requests.get(url=get_import_url,headers=self.headers)
            #
            #     if response.status_code != 200:
            #         print(response.content)
            #         return False
            #
            #     if response.json()['importState'] == "Succeeded":
            #         print("Import complete")
            #         return True
            #     else:
            #         print("Import in progress...")

    @staticmethod
    def force_raise_http_error(response: requests.Response) -> NoReturn:
        response.raise_for_status()
        raise requests.HTTPError(response)
