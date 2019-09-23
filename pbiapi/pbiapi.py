import datetime
import json
from typing import Callable

import requests


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
            print(f"Expected 200 response code when trying to set token, got {response.status_code}: {response.text}.")

    @property
    def workspaces(self):
        return self._workspaces or self.get_workspaces()

    @check_token
    def get_workspaces(self):
        url = "https://api.powerbi.com/v1.0/myorg/groups"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        if response.status_code == 200:
            self._workspaces = response.json()["value"]
            return self._workspaces
        else:
            raise requests.HTTPError(response)

    def find_workspace_id_by_name(self, name):
        if self._workspaces is not None:
            for item in self._workspaces:
                if item["name"] == name:
                    return item["id"]

    @check_token
    def createWorkspace(self,name):
        #Check if workspace exists already
        url = "https://api.powerbi.com/v1.0/myorg/groups?$filter=contains(name,'{name}')".format(name = name)
        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            return False
        else:
            #Dont reproduce workspace
            if response.json()['@odata.count'] > 0:
                print('Dataset already exists')
                return False
            #Try to create workspace
            else:
                print('Creating a workspace')
                url = "https://api.powerbi.com/v1.0/myorg/groups?workspaceV2=true"
                payload = {
                    "name":name
                }
                response = requests.post(url, data=payload, headers=self.headers)

                if response.status_code == 200:
                    print("Created workspace: ",name)
                    self.getWorkspaces()
                    return True
                else:
                    print("Error Creating workspace")
                    print(response.text)
                    return False

    @checkToken
    def addUsersToWorkspace(self,name,users):
        self.getWorkspaces()
        workspaceId = self.findWorkspaceIdByName(name)

        if workspaceId:
            url = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/users".format(groupId = workspaceId)

            response = requests.post(url, data=users, headers=self.headers)
            if response.status_code == 200:
                print("Added users to workspace")
                return True
            else:
                print("Error adding users to workspace")
                print(response.text)
                return False
        else:
            return False

    @checkToken
    def deleteWorkspace(self, workspaceName):
        workspaceId = self.findWorkspaceIdByName(workspaceName)

        if workspaceId == None:
            return False

        url = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}".format(groupId = workspaceId)

        response = requests.delete(url=url, headers=self.headers)

        if response.status_code == 200:
            print("Workspace Deleted")
            return True
        else:
            return False

    @check_token
    def get_datasets_in_workspace(self, workspace_id):
        datasets_url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets"
        response = requests.get(datasets_url, headers=self.headers)
        if response.status_code == 200:
            return response.json()["value"]

    def find_dataset_id_by_name(self, datasets, name):
        for item in datasets:
            if item["name"] == name:
                return item["id"]

    @check_token
    def refresh_dataset_by_id(self, workspace_id, dataset_id):
        url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/refreshes"
        payload = "notifyOption=NoNotification"
        response = requests.post(url, data=payload, headers=self.headers)

        if response.status_code != 202:
            print("Expected 202 response code, got {response.status_code}: {response.text}")

        return response.status_code == 202

    @check_token
    def create_push_dataset(self, workspace_id, schema, retention_policy):
        pushTable = (
            f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets?"
            f"defaultRetentionPolicy={retention_policy}"
        )
        payload = "notifyOption=NoNotification"
        response = requests.post(url, data=payload, headers=self.headers)

        if response.status_code != 202:
            print("Expected 202 response code, got {response.status_code}: {response.text}")

        return response.status_code == 202

    @check_token
    def create_dataset(self, workspace_id, schema, retention_policy):
        url = (
            f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets?"
            f"defaultRetentionPolicy={retention_policy}"
        )
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.post(url, json=schema, headers=headers)

        if response.status_code not in [201, 202]:
            print("Expected 201 or 202 response code, got {response.status_code}: {response.text}")

        return response.status_code in [201, 202]

    @check_token
    def delete_dataset(self, workspace_id, dataset_id):
        url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}"
        response = requests.delete(url, headers=self.headers)
        return response.status_code == 200

    @check_token
    def post_rows(self, workspace_id, dataset_id, table_name, data):
        url = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/datasets/{datasetId}/tables/{tableName}/rows".format(
            groupId=workspace_id, datasetId=dataset_id, tableName=table_name
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.token,
        }

        rowCount = len(data)
        rowCursor = 0

        while rowCursor < rowCount:
            tempCursor = 0
            if (rowCursor + 10000) < rowCount:
                tempCursor = rowCursor + 10000
            else:
                tempCursor = rowCount

            uploadData = json.dumps({"rows": data[rowCursor:tempCursor]})
            response = requests.post(url, data=uploadData, headers=headers)
            if response.status_code == 200:
                print(
                    "Added rows {start} to {finish}".format(
                        start=str(rowCursor), finish=str(tempCursor)
                    )
                )
            else:
                print(response.status_code)
                print(response.text)
                retry = 1
                while retry < 6:
                    print("Retry attempt: {attempt}".format(attempt=str(retry)))
                    response = requests.post(
                        url, data=uploadData, headers=headers
                    )
                    if response.status_code == 200:
                        print(
                            "Added rows {start} to {finish}".format(
                                start=str(rowCursor), finish=str(tempCursor)
                            )
                        )
                        break
                    else:
                        retry = retry + 1
                if retry > 5:
                    print("Error trying to add rows, aborting")
                    break

            rowCursor = tempCursor

    @check_token
    def updateTableSchema(self, workspace_id, dataset_id, table_name, schema):
        updateTableUrl = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/datasets/{datasetId}/tables/{tableName}".format(
            groupId=workspace_id, datasetId=dataset_id, tableName=table_name
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.token,
        }
        response = requests.put(
            updateTableUrl, data=json.dumps(schema), headers=headers
        )
        print(response.status_code)
        print(response.text)

    @check_token
    def getTables(self, workspace_id, dataset_id):
        tablesUrl = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/datasets/{datasetId}/tables".format(
            groupId=workspace_id, datasetId=dataset_id
        )
        response = requests.get(tablesUrl, headers=self.headers)

        if response.status_code == 200:
            return response.json()
        else:
            return None

    @check_token
    def truncateTable(self, workspace_id, dataset_id, table_name):
        truncateTableUrl = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/datasets/{datasetId}/tables/{tableName}/rows".format(
            groupId=workspace_id, datasetId=dataset_id, tableName=table_name
        )

        response = requests.delete(truncateTableUrl, headers=self.headers)

        if response.status_code == 200:
            return True
        else:
            return False

    #------REPORT FUNCTIONS------

    @checkToken
    def getReportsInWorkspace(self,workspaceName):
        workspaceId = self.findWorkspaceIdByName(workspaceName)

        if workspaceId == None:
            return None

        url = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/reports".format(groupId = workspaceId)
        response = requests.get(url=url,headers=self.headers)

        if response.status_code == 200:
            return response.json()['value']

    def findReportIdByName(self,reports,name):
        return next((item['id'] for item in reports if item["name"] == name),None)



    @checkToken
    def deleteReport(self,workspaceName,reportName):
        workspaceId = self.findWorkspaceIdByName(workspaceName)

        if workspaceId == None:
            return False
        reports = self.getReportsInWorkspace(workspaceName)
        reportId = self.findReportIdByName(reports,reportName)

        if reportId == None:
            return False

        url = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/reports/{reportId}".format(groupId = workspaceId, reportId = reportId)
        response = requests.delete(url = url, headers = self.headers)

        if response.status_code == 200:
            print("Report deleted")
            return True
        else:
            return False



    #------IMPORT DATASETS AND REPORTS------
    @checkToken
    def importFileIntoWorkspace(self, workspaceName, skipReport, filePath, displayName):

        workspaceId = self.findWorkspaceIdByName(workspaceName)

        #Check for workspace
        if workspaceId == None:
            return False

        url = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/imports?datasetDisplayName={datasetDisplayName}&nameConflict={nameConflict}&skipReport={skipReport}".format(
            groupId = workspaceId,
            nameConflict = 'CreateOrOverwrite',
            skipReport = skipReport,
            datasetDisplayName = displayName
        )

        headers = {
            'Content-Type': "multipart/form-data",
            'Authorization': "Bearer " + self.token
        }

        #Attempt to load the file
        try:
            files = {
                'filename': open(filePath, 'rb')
            }
        except:
            print('Could not open file')
            return False


        response = requests.post(url=url,headers=headers,files=files)

        if response.status_code == 202:
            print(response.json())
            importId = response.json()['id']
            print("File Uploading. Id: ",importId)
            return True
        else:
            return False

            # This code doesnt work yet, keeps returning 403
            # get_import_url = "https://api.powerbi.com/v1.0/myorg/imports/{importId}".format(importId = importId)
            # print(get_import_url)

            # while True:
            #     response = requests.get(url=get_import_url,headers=self.headers)

            #     if response.status_code != 200:
            #         print(response.content)
            #         return False

            #     if response.json()['importState'] == "Succeeded":
            #         print("Import complete")
            #         return True
            #     else:
            #         print("Import in progress...")
