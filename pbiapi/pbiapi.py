import datetime
import json
import logging
import os
from typing import Callable, Dict, List, NoReturn, Union
from urllib import parse

import requests

from pbiapi.utils import partition

HTTP_OK_CODE = 200
HTTP_ACCEPTED_CODE = 202


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
    def find_entity_id_by_name(
        entity_list: List,
        name: str,
        entity_type: str,
        raise_if_missing: bool = False,
        attribute_name_alias: str = "name",
        attribute_alias: str = "id",
    ) -> str:
 #       print('lower name=%s' % name.lower())
        for item in entity_list:
 #           print('item[attribute_name_alias].lower()=%s' % item[attribute_name_alias].lower())
            if item[attribute_name_alias].lower() == name.lower():
                return item[attribute_alias]
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
#            print(response.json())
            return response.json()["value"][0]['id']

        # Workspace does not exist, lets create it:
        logging.info(f"Trying to create a workspace with name: {name}...")
        url = self.base_url + "groups?workspaceV2=true"
        response = requests.post(url, data={"name": name}, headers=self.headers)

        if response.status_code == HTTP_OK_CODE:
            logging.info("Workspace created successfully!")
            self.get_workspaces()  # Update internal state
 #           print(response.json())
            return response.json()['id']
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
    def get_datasets(self) -> List:

        datasets_url = self.base_url + f"datasets"
        response = requests.get(datasets_url, headers=self.headers)
        response.raise_for_status()
        if response.status_code == HTTP_OK_CODE:
            return response.json()["value"]

    @check_token
    def refresh_dataset_by_id(self, workspace_id: str, dataset_id: str) -> None:
        url = self.base_url + f"groups/{workspace_id}/datasets/{dataset_id}/refreshes"
        response = requests.post(url, data="notifyOption=NoNotification", headers=self.headers)

        if response.status_code == 202:
            logging.info(f"Dataset with id {dataset_id} (and workspace id {workspace_id}) was updated!")
        else:
            logging.error("Dataset refresh failed!")
            self.force_raise_http_error(response, expected_codes=202)

    @check_token
    def refresh_dataset_by_name(self, workspace_name: str, dataset_name: str) -> None:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)
        datasets = self.get_datasets_in_workspace(workspace_name)
        dataset_id = self.find_entity_id_by_name(datasets, dataset_name, "dataset", True)
        self.refresh_dataset_by_id(workspace_id, dataset_id)

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
        workspace_id, dataset_id = self.get_workspace_and_dataset_id(workspace_name, dataset_name)

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
    def get_reports_in_workspace_by_id(self, workspace_id: str) -> List:
 
        url = self.base_url + f"groups/{workspace_id}/reports"
        response = requests.get(url, headers=self.headers)

        if response.status_code == HTTP_OK_CODE:
            return response.json()["value"]

    @check_token
    def rebind_report_in_workspace(self, workspace_name: str, dataset_name: str, report_name: str) -> None:
        workspace_id, dataset_id = self.get_workspace_and_dataset_id(workspace_name, dataset_name)

        reports = self.get_reports_in_workspace(workspace_name)
        report_id = self.find_entity_id_by_name(reports, report_name, "report", raise_if_missing=True)

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
            logging.error("Report deletion failed!")
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
                return response
            else:
                logging.info("Import in progress...")

    @check_token
    def update_parameters_in_dataset(self, workspace_name: str, dataset_name: str, parameters: list):
        workspace_id, dataset_id = self.get_workspace_and_dataset_id(workspace_name, dataset_name)

        update_details = {"updateDetails": parameters}
        url = self.base_url + f"groups/{workspace_id}/datasets/{dataset_id}/UpdateParameters"
        headers = {"Content-Type": "application/json", **self.get_auth_header()}
        response = requests.post(url, json=update_details, headers=headers)

        if response.status_code == HTTP_OK_CODE:
            for parameter in parameters:
                logging.info(
                    f"Parameter \"{parameter['name']}\"",
                    f" updated to \"{parameter['newValue']}\"",
                    f" in Dataset named '{dataset_name}' in workspace '{workspace_name}'!",
                )
        else:
            logging.error(f"Parameter update failed for dataset {dataset_name}!")
            self.force_raise_http_error(response)


    @check_token
    def update_parameters_in_dataset_by_id(self, workspace_id: str, dataset_id: str, parameters: list):
        update_details = {"updateDetails": parameters}
        url = self.base_url + f"groups/{workspace_id}/datasets/{dataset_id}/UpdateParameters"
        headers = {"Content-Type": "application/json", **self.get_auth_header()}
        response = requests.post(url, json=update_details, headers=headers)

        if response.status_code == HTTP_OK_CODE:
            for parameter in parameters:
                logging.info(
                    f"Parameter \"{parameter['name']}\"",
                    f" updated to \"{parameter['newValue']}\"",
                    f" in Dataset named '{dataset_id}' in workspace '{workspace_id}'!",
                )
        else:
            logging.error(f"Parameter update failed for dataset {dataset_id}!")
            self.force_raise_http_error(response)

    @check_token
    def get_parameters_in_dataset(self, workspace_name: str, dataset_name: str) -> List:
        workspace_id, dataset_id = self.get_workspace_and_dataset_id(workspace_name, dataset_name)

        url = self.base_url + f"groups/{workspace_id}/datasets/{dataset_id}/parameters"

        response = requests.get(url, headers=self.headers)

        if response.status_code == HTTP_OK_CODE:
            return response.json()["value"]
        else:
            logging.error(f"Failed to get parameters for dataset {dataset_name}!")
            self.force_raise_http_error(response)

    @check_token
    def take_over_dataset(self, workspace_name: str, dataset_name: str) -> None:
        workspace_id, dataset_id = self.get_workspace_and_dataset_id(workspace_name, dataset_name)

        url = self.base_url + f"groups/{workspace_id}/datasets/{dataset_id}/TakeOver"

        response = requests.post(url, headers=self.headers)

        if response.status_code == HTTP_OK_CODE:
            logging.info(f"Takeover of dataset {dataset_name} Complete")
        else:
            logging.error(f"Takeover of dataset {dataset_name} failed!")
            self.force_raise_http_error(response)

    @check_token
    def get_dataset_refresh_history(self, workspace_name: str, dataset_name: str, top=10) -> List:
        workspace_id, dataset_id = self.get_workspace_and_dataset_id(workspace_name, dataset_name)

        url = self.base_url + f"groups/{workspace_id}/datasets/{dataset_id}/refreshes?$top={top}"

        response = requests.get(url, headers=self.headers)

        if response.status_code in [HTTP_OK_CODE, HTTP_ACCEPTED_CODE]:
            return response.json()["value"]
        else:
            logging.error(f"Failed getting refresh history for {dataset_name}!")
            self.force_raise_http_error(response)

    @staticmethod
    def force_raise_http_error(
        response: requests.Response, expected_codes: Union[List[int], int] = HTTP_OK_CODE
    ) -> NoReturn:
        logging.error(f"Expected response code(s) {expected_codes}, got {response.status_code}: {response.text}.")
        response.raise_for_status()
        raise requests.HTTPError(response)

    def get_workspace_and_dataset_id(self, workspace_name: str, dataset_name: str) -> Union:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)
 #       print("workspace_id=%s" % workspace_id)
        datasets = self.get_datasets_in_workspace(workspace_name)
 #       print("datasets=%s" % datasets)
        dataset_id = self.find_entity_id_by_name(datasets, dataset_name, "dataset", raise_if_missing=True)

        return workspace_id, dataset_id

    @check_token
    def get_pipelines(self) -> List:
        url = self.base_url + "pipelines"
        print(url)
        response = requests.get(url, headers=self.headers)
        if response.status_code == HTTP_OK_CODE:
            self._workspaces = response.json()["value"]
            return self._workspaces
        else:
            logging.error("Failed to fetch pipelines!")
            self.force_raise_http_error(response)

    @check_token
    def get_pipeline(self, pipeline_id: str) -> List:
        url = self.base_url + f"pipelines/{pipeline_id}"
        response = requests.get(url, headers=self.headers)
 #       print(response.json())
        if response.status_code == HTTP_OK_CODE:
            self._workspaces = response.json()
            return self._workspaces
        else:
            logging.error("Failed to fetch pipeline!")
            self.force_raise_http_error(response)

    @check_token
    def get_pipeline_by_name(self, pipeline_name) -> List:
        pipelines_list = self.get_pipelines()
        pipeline_id = self.find_entity_id_by_name(
            pipelines_list, pipeline_name, "pipelines", raise_if_missing=True, attribute_name_alias="displayName"
        )
        print("pipeline id: %s" % pipeline_id)
        return self.get_pipeline(pipeline_id)

    @check_token
    def get_pipeline_operations(self, pipeline_id: str) -> List:
        url = self.base_url + f"pipelines/{pipeline_id}/operations"
        response = requests.get(url, headers=self.headers)
        if response.status_code == HTTP_OK_CODE:
            self._workspaces = response.json()["value"]
            return self._workspaces
        else:
            logging.error("Failed to fetch pipeline operations!")
            self.force_raise_http_error(response)

    @check_token
    def get_pipeline_operations_by_name(self, pipeline_name: str) -> List:
        pipelines_list = self.get_pipelines()
        pipeline_id = self.find_entity_id_by_name(
            pipelines_list, pipeline_name, "pipelines", raise_if_missing=True, attribute_name_alias="displayName"
        )
        print("pipeline id: %s" % pipeline_id)
        return self.get_pipeline_operations(pipeline_id)

    @check_token
    def clone_report_by_name(
        self,
        workspace_name: str,
        report_name: str,
        new_report_name: str,
        target_work_space_name: str = None,
        target_model_id: str = None,
    ) -> None:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)
        workspace_reports = self.get_reports_in_workspace(workspace_name)
        report_id = self.find_entity_id_by_name(workspace_reports, report_name, "reports", raise_if_missing=True)
        url = self.base_url + f"groups/{workspace_id}/reports/{report_id}/Clone"
        data = {}
        data["Name"] = new_report_name
        if target_work_space_name != None:
            target_workspace_id = self.find_entity_id_by_name(
                self.workspaces, target_work_space_name, "workspace", raise_if_missing=True
            )
            data["targetWorkspaceId"] = target_workspace_id
        if target_model_id != None:
            data["targetModelId"] = target_model_id
        #       data="Name=" + new_report_name
        response = requests.post(url, data=data, headers=self.headers)

        if response.status_code == 200:
            logging.info(f"report  {report_id} from workspace {workspace_name}) was cloned ")
            return response.json()
        else:
            logging.error("Dataset refresh failed!")
            self.force_raise_http_error(response, expected_codes=200)

    @check_token
    def get_dataset_datasources(self, workspace_id, dataset_id) -> List:
        url = self.base_url + f"groups/{workspace_id}/datasets/{dataset_id}/datasources"
        response = requests.get(url, headers=self.headers)

        if response.status_code == HTTP_OK_CODE:
            self._workspaces = response.json()["value"]
            return self._workspaces
        else:
            logging.error("Failed to datasources!")
            self.force_raise_http_error(response)

    @check_token
    def get_dataset_datasources_by_name(self, workspace_name, dataset_name) -> List:
        workspace_id, dataset_id = self.get_workspace_and_dataset_id(workspace_name, dataset_name)
        print("workspace_id: %s , dataset id: %s" % (workspace_id, dataset_id))
        return self.get_dataset_datasources(workspace_id, dataset_id)

    @check_token
    def update_datasource(self, gateway_id: str, datasource_id: str, user_name: str, password: str):

        url = self.base_url + f"gateways/{gateway_id}/datasources/{datasource_id}"
        headers = {"Content-Type": "application/json", **self.get_auth_header()}

        credentialDetails = {
            "credentialType": "Basic",
            "encryptedConnection": "Encrypted",
            "encryptionAlgorithm": "None",
            "privacyLevel": "None",
            "useEndUserOAuth2Credentials": "False",
        }

        credentials = {}
        credentials["credentialData"] = [
            {"name": "username", "value": user_name},
            {"name": "password", "value": password},
        ]
        credentialDetails["credentials"] = str(credentials)
        data = {"credentialDetails": credentialDetails}

        response = requests.patch(url, headers=headers, json=data)
        if response.status_code == HTTP_OK_CODE:
            logging.info(f"update credentials Complete")
        else:
            logging.error(f"update credentials failed for gateway_id {gateway_id} and  datasource_id {datasource_id}!")
            self.force_raise_http_error(response)

    @check_token
    def execute_queries(self, dataset_id: str, query_list: list, serializerSettings: dict) -> None:

        body = {"queries": query_list, "serializerSettings": serializerSettings}
        # Workspace exists, lets add user:
        url = self.base_url + f"datasets/{dataset_id}/executeQueries"
        print("url=%s" % url)
        headers = {"Content-Type": "application/json", **self.get_auth_header()}
        print("json=%s" % json)
        response = requests.post(url, json=body, headers=headers)

        if response.status_code == HTTP_OK_CODE:
            logging.info(f"success execute_queries")
            return json.loads(response.text.encode("utf8"))
        else:
            logging.error(f"Failed to execute_queries': {json}")
            self.force_raise_http_error(response)

    @check_token
    def execute_queries_by_name(
        self, workspace_name: str, dataset_name: str, query_list: list, serializerSettings: dict
    ) -> None:
        datasets = self.get_datasets_in_workspace(workspace_name)
        dataset_id = self.find_entity_id_by_name(datasets, dataset_name, "dataset", True)
        return self.execute_queries(dataset_id=dataset_id, query_list=query_list, serializerSettings=serializerSettings)

    @check_token
    def bind_to_gateway(self, dataset_Id: str, gateway_id: str) -> None:
        # 403: {"Message":"API is not accessible for application"}
        url = self.base_url + f"datasets/{dataset_Id}/Default.BindToGateway"
        gatewayObject = {"gatewayObjectId": gateway_id}
        response = requests.post(url, json=gatewayObject, headers=self.headers)

        if response.status_code == HTTP_OK_CODE:
            logging.info(f"Takeover of dataset {dataset_Id} Complete")
        else:
            logging.error(f"Takeover of dataset {dataset_Id} failed!")
            self.force_raise_http_error(response)

    @check_token
    def get_workspace_and_report_id(self, workspace_name: str, report_name: str) -> Union:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)
        print("workspace_id=%s" % workspace_id)
        reports = self.get_reports_in_workspace(workspace_name)
        print("datasets=%s" % reports)
        report_id = self.find_entity_id_by_name(
            reports, report_name, "report", raise_if_missing=True, attribute_name_alias="name", attribute_alias="id"
        )
        dataset_id = self.find_entity_id_by_name(
            reports,
            report_name,
            "report",
            raise_if_missing=True,
            attribute_name_alias="name",
            attribute_alias="datasetId",
        )

        return workspace_id, report_id, dataset_id

    def get_dataset_in_workspace(self, workspace_name: str, dataset_id: str) -> List:
        workspace_id = self.find_entity_id_by_name(self.workspaces, workspace_name, "workspace", raise_if_missing=True)

        datasets_url = self.base_url + f"groups/{workspace_id}/datasets/{dataset_id}"
        response = requests.get(datasets_url, headers=self.headers)
        response.raise_for_status()
        if response.status_code == HTTP_OK_CODE:
            return response.json()

    @check_token
    def get_datasets_in_workspace_by_id(self, workspace_id: str) -> List:
        datasets_url = self.base_url + f"groups/{workspace_id}/datasets"
        response = requests.get(datasets_url, headers=self.headers)
        response.raise_for_status()
        if response.status_code == HTTP_OK_CODE:
            return response.json()["value"]           
    def print_all_datasources(self):        
        for ws in self.workspaces:
            wsname=ws['name']
            dss=self.get_datasets_in_workspace_by_id(ws['id'])
            print ('ws name: %s, ws id: %s' % (wsname, ws['id']) )
            for ds in dss:
                print ('   dataset=%s datasetId=%s' % (ds['name'], ds['id']))
                datasource=self.get_dataset_datasources(ws['id'], ds['id'])
                print ('         datasource: %s' % datasource)
            
    @staticmethod
    def find_entity_by_name(
        entity_list: List,
        name: str,
        entity_type: str,
        raise_if_missing: bool = False,
        attribute_name_alias: str = "name",
        attribute_alias: str = "id",
    ) -> str:
        for item in entity_list:
            if item[attribute_name_alias].lower() == name.lower():
                return item
        if raise_if_missing:
            raise RuntimeError(f"No {entity_type} was found with the name: '{name}'")

    def get_report_by_workspace_id_and_report_id(self, workspace_id: str, report_id: str) -> dict:
        
        url = self.base_url + f"groups/{workspace_id}/reports/{report_id}"
        response = requests.get(url, headers=self.headers)

        if response.status_code == HTTP_OK_CODE:
            return response.json()

    @check_token
    def rebind_report_in_workspace_by_id(self, workspace_id: str, dataset_id: str, report_id: str) -> None:

        url = self.base_url + f"groups/{workspace_id}/reports/{report_id}/Rebind"
        headers = {"Content-Type": "application/json", **self.get_auth_header()}
        payload = {"datasetId": dataset_id}

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == HTTP_OK_CODE:
            logging.info(f"Report named '{report_id}' rebound to dataset with name '{dataset_id}'")
        else:
            logging.error(f"Failed to rebind report with name '{report_id}' to dataset with name '{dataset_id}'")
            self.force_raise_http_error(response)


    @check_token
    def clone_report_by_id(
        self,
        workspace_id: str,
        report_id: str,
        new_report_name: str,
        target_workspace_id: str = None,
        target_model_id: str = None,
    ) -> None:
        url = self.base_url + f"groups/{workspace_id}/reports/{report_id}/Clone"
        data = {}
        data["Name"] = new_report_name
        if target_workspace_id != None:
            data["targetWorkspaceId"] = target_workspace_id
        if target_model_id != None:
            data["targetModelId"] = target_model_id
        response = requests.post(url, data=data, headers=self.headers)

        if response.status_code == 200:
            logging.info(f"report  {report_id} from workspace {workspace_id}) was cloned ")
            return response.json()
        else:
            logging.error("Dataset refresh failed!")
            self.force_raise_http_error(response, expected_codes=200)


    @check_token
    def get_dataset_by_ws_id_and_ds_name(self, workspace_id: str, dataset_name: str) -> None:
        datasets = self.get_datasets_in_workspace_by_id(workspace_id)
        dataset = self.find_entity_by_name(datasets, dataset_name, "dataset", True)
        return (dataset)