import datetime
import logging
import os
from typing import Callable, Dict, List, NoReturn, Union
from urllib import parse

import requests

from pbiapi.utils import partition

HTTP_OK_CODE = 200


def check_token(fn: Callable) -> Callable:
    def wrapper(pbi_client, *args, **kwargs):
        if pbi_client.token is None or pbi_client.token_expiration < datetime.datetime.utcnow():
            pbi_client.update_token()
        return fn(pbi_client, *args, **kwargs)

    return wrapper


class PowerBIAPIClient:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://api.powerbi.com/v1.0/myorg/"
        self.url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        self.token = None
        self.token_expiration = None
        self._workspaces = None
        self.headers = None

    def get_auth_header(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def update_token(self) -> None:
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "scope": "https://analysis.windows.net/powerbi/api/.default",
            "client_secret": self.client_secret,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = requests.post(self.url, data=payload, headers=headers)

        if response.status_code == HTTP_OK_CODE:
            self.token = response.json()["access_token"]
            self.token_expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
            self.headers = {**headers, **self.get_auth_header()}
        else:
            self.force_raise_http_error(response)

    @property
    def workspaces(self) -> List:
        return self._workspaces or self.get_workspaces()

    @check_token
    def get_workspaces(self) -> List:
        url = self.base_url + "groups"
        response = requests.get(url, headers=self.headers)

        if response.status_code == HTTP_OK_CODE:
            self._workspaces = response.json()["value"]
            return self._workspaces
        else:
            logging.error("Failed to fetch workspaces!")
            self.force_raise_http_error(response)

    @staticmethod
    def find_entity_id_by_name(entity_list: List, name: str, entity_type: str, raise_if_missing: bool = False) -> str:
        for item in entity_list:
            if item["name"] == name:
                return item["id"]
        if raise_if_missing:
            raise RuntimeError(f"No {entity_type} was found with the name: '{name}'")

    @check_token
    def create_workspace(self, name: str) -> None:
        # Check if workspace exists already:
        url = self.base_url + "groups?$filter=" + parse.quote(f"name eq '{name}'")
        response = requests.get(url, headers=self.headers)

        if response.status_code != HTTP_OK_CODE:
            logging.error(f"Failed when checking if the workspace, '{name}' already exists!")
            self.force_raise_http_error(response)

        if response.json()["@odata.count"] > 0:
            logging.info("Workspace already exists, no changes made!")
            return

        # Workspace does not exist, lets create it:
        logging.info(f"Trying to create a workspace with name: {name}...")
        url = self.base_url + "groups?workspaceV2=true"
        response = requests.post(url, data={"name": name}, headers=self.headers)

        if response.status_code == HTTP_OK_CODE:
            logging.info("Workspace created successfully!")
            self.get_workspaces()  # Update internal state
        else:
            logging.error(f"Failed to create the new workspace: '{name}':")
            self.force_raise_http_error(response)

    @check_token
    def add_user_to_workspace(self, workspace_name: str, user: Dict) -> None:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)

        # Workspace exists, lets add user:
        url = self.base_url + f"groups/{workspace_id}/users"
        response = requests.post(url, data=user, headers=self.headers)

        if response.status_code == HTTP_OK_CODE:
            logging.info(f"Added users to workspace '{workspace_name}'")
        else:
            logging.error(f"Failed to add user to workspace '{workspace_name}': {user}")
            self.force_raise_http_error(response)

    @check_token
    def get_users_from_workspace(self, name: str) -> List:
        workspace_id = self.find_entity_id_by_name(self.workspaces, name, "workspace", raise_if_missing=True)

        url = self.base_url + f"groups/{workspace_id}/users"

        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()["value"]
        else:
            logging.error("Error getting users from workspace")
            self.force_raise_http_error(response)

    @check_token
    def delete_workspace(self, workspace_name: str) -> None:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace")

        if workspace_id is None:
            # If workspace is already deleted / doesn't exist, we simply return:
            return

        url = self.base_url + f"groups/{workspace_id}"
        response = requests.delete(url, headers=self.headers)

        if response.status_code == HTTP_OK_CODE:
            logging.info("Workspace deleted successfully!")
        else:
            logging.error("Workspace deletion failed:")
            self.force_raise_http_error(response)

    @check_token
    def get_datasets_in_workspace(self, workspace_name: str) -> List:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)

        datasets_url = self.base_url + f"groups/{workspace_id}/datasets"
        response = requests.get(datasets_url, headers=self.headers)
        response.raise_for_status()
        if response.status_code == HTTP_OK_CODE:
            return response.json()["value"]

    @check_token
    def refresh_dataset_by_id(self, workspace_name: str, dataset_id: str) -> None:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)
        url = self.base_url + f"groups/{workspace_id}/datasets/{dataset_id}/refreshes"
        response = requests.post(url, data="notifyOption=NoNotification", headers=self.headers)

        if response.status_code == 202:
            logging.info(f"Dataset with id {dataset_id} (and workspace id {workspace_id}) was updated!")
        else:
            logging.error("Dataset refresh failed!")
            self.force_raise_http_error(response, expected_codes=202)

    @check_token
    def refresh_dataset_by_name(self, workspace_name: str, dataset_name: str) -> None:
        datasets = self.get_datasets_in_workspace(workspace_name)
        dataset_id = self.find_entity_id_by_name(datasets, dataset_name, "dataset", True)
        self.refresh_dataset_by_id(workspace_name, dataset_id)

    @check_token
    def create_push_dataset(self, workspace_name: str, retention_policy: str) -> None:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)
        url = self.base_url + f"groups/{workspace_id}/datasets?defaultRetentionPolicy={retention_policy}"
        response = requests.post(url, data="notifyOption=NoNotification", headers=self.headers)

        if response.status_code == 202:
            logging.info(
                f"Create push dataset successful using workspace_id: {workspace_id} and "
                f"retention_policy: {retention_policy}"
            )
        else:
            logging.error("Create push dataset failed!")
            self.force_raise_http_error(response, expected_codes=202)

    @check_token
    def create_dataset(self, workspace_name: str, schema: Dict, retention_policy: str) -> None:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)
        url = self.base_url + f"groups/{workspace_id}/datasets?defaultRetentionPolicy={retention_policy}"
        response = requests.post(url, json=schema, headers=self.get_auth_header())

        if response.status_code in [201, 202]:
            logging.info(
                f"Create dataset successful using workspace_id: {workspace_id}, schema: {schema} "
                f"and retention_policy: {retention_policy}"
            )
        else:
            logging.error("Failed to create dataset!")
            self.force_raise_http_error(response, expected_codes=[201, 202])

    @check_token
    def delete_dataset(self, workspace_name: str, dataset_name: str) -> None:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)

        datasets = self.get_datasets_in_workspace(workspace_name)
        dataset_id = self.find_entity_id_by_name(datasets, dataset_name, "dataset", raise_if_missing=True)

        url = self.base_url + f"groups/{workspace_id}/datasets/{dataset_id}"
        response = requests.delete(url, headers=self.headers)
        if response.status_code == HTTP_OK_CODE:
            logging.info("Dataset with id: {dataset_id} in workspace with id: {workspace_id} deleted successfully!")
        else:
            logging.error("Failed to delete dataset!")
            self.force_raise_http_error(response)

    @check_token
    def post_rows(self, workspace_name: str, dataset_id: str, table_name: str, data, chunk_size: int = 10000) -> None:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)
        url = self.base_url + f"groups/{workspace_id}/datasets/{dataset_id}/tables/{table_name}/rows"

        chunked_data = partition(data, n=chunk_size)
        tot_chunks = len(chunked_data)

        for i, row_chunk in enumerate(chunked_data, 1):
            response = requests.post(url, json={"rows": row_chunk}, headers=self.get_auth_header())
            if response.status_code == HTTP_OK_CODE:
                logging.info(f"Chunk [{i}/{tot_chunks}] inserted successfully! Size: {len(row_chunk)} rows")
            else:
                logging.error("Row insertion failed!")
                self.force_raise_http_error(response)

    @check_token
    def update_table_schema(self, workspace_name: str, dataset_id: str, table_name: str, schema: Dict) -> None:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)
        url = self.base_url + f"groups/{workspace_id}/datasets/{dataset_id}/tables/{table_name}"
        response = requests.put(url, json=schema, headers=self.get_auth_header())
        # TODO(scottmelhop): Use/check/raise depending on status code?
        logging.info(f"Update table schema returned status code {response.status_code}: {response.text}")

    @check_token
    def get_tables(self, workspace_name: str, dataset_id: str) -> List:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)
        url = self.base_url + f"groups/{workspace_id}/datasets/{dataset_id}/tables"
        response = requests.get(url, headers=self.headers)

        if response.status_code == HTTP_OK_CODE:
            return response.json()

    @check_token
    def truncate_table(self, workspace_name: str, dataset_id: str, table_name: str) -> None:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)
        url = self.base_url + f"groups/{workspace_id}/datasets/{dataset_id}/tables/{table_name}/rows"
        response = requests.delete(url, headers=self.headers)

        if response.status_code == HTTP_OK_CODE:
            logging.info("Table truncation successful!")
        else:
            logging.error("Table truncation failed!")
            self.force_raise_http_error(response)

    @check_token
    def get_reports_in_workspace(self, workspace_name: str) -> List:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)

        url = self.base_url + f"groups/{workspace_id}/reports"
        response = requests.get(url, headers=self.headers)

        if response.status_code == HTTP_OK_CODE:
            return response.json()["value"]

    @check_token
    def rebind_report_in_workspace(self, workspace_name: str, dataset_name: str, report_name: str) -> None:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)

        reports = self.get_reports_in_workspace(workspace_name)
        report_id = self.find_entity_id_by_name(reports, report_name, "report", raise_if_missing=True)

        datasets = self.get_datasets_in_workspace(workspace_name)
        dataset_id = self.find_entity_id_by_name(datasets, dataset_name, "dataset", raise_if_missing=True)

        url = self.base_url + f"groups/{workspace_id}/reports/{report_id}/Rebind"
        headers = {"Content-Type": "application/json", **self.get_auth_header()}
        payload = {"datasetId": dataset_id}

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == HTTP_OK_CODE:
            logging.info(f"Report named '{report_name}' rebound to dataset with name '{dataset_name}'")
        else:
            logging.error(f"Failed to rebind report with name '{report_name}' to dataset with name '{dataset_name}'")
            self.force_raise_http_error(response)

    @check_token
    def delete_report(self, workspace_name: str, report_name: str) -> None:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)

        reports = self.get_reports_in_workspace(workspace_name)
        report_id = self.find_entity_id_by_name(reports, report_name, "report", raise_if_missing=True)

        url = self.base_url + f"groups/{workspace_id}/reports/{report_id}"
        response = requests.delete(url, headers=self.headers)

        if response.status_code == HTTP_OK_CODE:
            logging.info(f"Report named '{report_name}' in workspace '{workspace_name}' deleted successfully!")
        else:
            logging.error(f"Report deletion failed!")
            self.force_raise_http_error(response)

    @check_token
    def import_file_into_workspace(
        self, workspace_name: str, skip_report: bool, file_path: str, display_name: str
    ) -> None:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)

        if not os.path.isfile(file_path):
            raise FileNotFoundError(2, f"No such file or directory: '{file_path}'")

        name_conflict = "CreateOrOverwrite"
        url = (
            self.base_url
            + f"groups/{workspace_id}/imports?datasetDisplayName={display_name}&nameConflict="
            + f"{name_conflict}"
            + ("&skipReport=true" if skip_report else "")
        )
        headers = {"Content-Type": "multipart/form-data", **self.get_auth_header()}

        with open(file_path, "rb") as f:
            response = requests.post(url, headers=headers, files={"filename": f})

        if response.status_code == 202:
            logging.info(response.json())
            import_id = response.json()["id"]
            logging.info(f"File uploading with id: {import_id}")
        else:
            self.force_raise_http_error(response)

        get_import_url = self.base_url + f"groups/{workspace_id}/imports/{import_id}"

        while True:
            response = requests.get(url=get_import_url, headers=self.headers)
            if response.status_code != 200:
                self.force_raise_http_error(response)

            if response.json()["importState"] == "Succeeded":
                logging.info("Import complete")
                return
            else:
                logging.info("Import in progress...")

    @staticmethod
    def force_raise_http_error(
        response: requests.Response, expected_codes: Union[List[int], int] = HTTP_OK_CODE
    ) -> NoReturn:
        logging.error(f"Expected response code(s) {expected_codes}, got {response.status_code}: {response.text}.")
        response.raise_for_status()
        raise requests.HTTPError(response)
