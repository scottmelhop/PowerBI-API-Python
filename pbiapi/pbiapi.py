import requests

class PowerBiApiClient:    

    def __init__(self,tenant_id,client_id,client_secret):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.url = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token".format(tenant_id=self.tenant_id)
        self.token = None
        self.workspaces = None

    def setToken(self):
        payload = {
            "grant_type" : "client_credentials",
            "client_id" : self.client_id,
            "scope" : "https://analysis.windows.net/powerbi/api/.default",
            "client_secret" : self.client_secret
        }
        headers = {
            'Content-Type': "application/x-www-form-urlencoded",
        }

        response = requests.request("POST", self.url, data=payload, headers=headers)

        if response.status_code == 200:
            self.token = response.json()['access_token']
            return True
        else:
            print(response.status_code)
            print(response.text)
            return False

     
    def getWorkspaces(self):
        if self.token == None:
            return False
        else:            
            url = "https://api.powerbi.com/v1.0/myorg/groups"
            headers = {
                'Authorization': "Bearer " + self.token
                }
            response = requests.request("GET", url, headers=headers)

            if response.status_code == 200:
                self.workspaces = response.json()['value']
                return True
            else:
                return False
    
    def findWorkspaceIdByName(self,name):
        if self.workspaces != None:
            return next((item['id'] for item in self.workspaces if item["name"] == name),None)
        else:
            return None
    
    def getDatasetsInWorkspace(self,workspace_id):
        datasets_url = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/datasets".format(groupId = workspace_id)
        if self.token != None:
            headers = {
                    'Authorization': "Bearer " + self.token
                    }                
            response = requests.request("GET", datasets_url, headers=headers)
            if response.status_code == 200:
                return response.json()['value']
            else:
                return None

        else:
            return None
    
    def findDatasetIdByName(self,datasets,name):
        return next((item['id'] for item in datasets if item["name"] == name),None)
        
    def refreshDatasetById(self,workspace_id,dataset_id):
        dataset_refresh = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/datasets/{datasetId}/refreshes".format(
                    groupId = workspace_id, 
                    datasetId = dataset_id
            )
        headers = {
            'Content-Type': "application/x-www-form-urlencoded",
            'Authorization': "Bearer " + self.token
        }
        payload = "notifyOption=NoNotification"
        response = requests.request("POST", dataset_refresh, data=payload, headers=headers)

        if response.status_code == 202:
            return True
        else:
            print(response.status_code)
            print(response.text)
            return False
    
    def createDataset(self,workspace_id,schema):
        pushTable = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/datasets?defaultRetentionPolicy=basicFIFO".format(
            groupId = workspace_id            
        )

        headers = {
           
            'Authorization': "Bearer " + self.token
        } 
        response = requests.request("POST", pushTable, data=schema, headers=headers)

        if response.status_code == 201 or response.status_code == 202:
            return True
        else:
            return False
        

    def deleteDataset(self,workspace_id,dataset_id):
        deleteUrl = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/datasets/{datasetId}".format(
            groupId = workspace_id,
            datasetId = dataset_id
        )
        headers = {           
            'Authorization': "Bearer " + self.token
        }
        response = requests.request("DELETE",deleteUrl,headers=headers)
        if response.status_code == 200:
            return True
        else:
            return False

    def postRows(self,workspace_id,dataset_id,table_name,rows):
        postRowsUrl = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/datasets/{datasetId}/tables/{tableName}/rows".format(
            groupId = workspace_id,
            datasetId = dataset_id,
            tableName = table_name
        )
        headers = {           
            'Authorization': "Bearer " + self.token
        }
        response = requests.request("POST", postRowsUrl, data=rows, headers=headers)
        if response.status_code == 200:
            return True
        else:
            return False

    def updateTableSchema(self,workspace_id,dataset_id,table_name,schema):
        updateTableUrl = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/datasets/{datasetId}/tables/{tableName}".format(
            groupId = workspace_id,
            datasetId = dataset_id,
            tableName = table_name
        )
        headers = {
            'Content-Type': "application/json",           
            'Authorization': "Bearer " + self.token
        }
        response = requests.request("PUT", updateTableUrl, data=schema, headers=headers)
        print(response.status_code)
        print(response.text)
    
    def getTables(self,workspace_id,dataset_id):
        tablesUrl = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/datasets/{datasetId}/tables".format(
            groupId = workspace_id,
            datasetId = dataset_id
        )
        headers = {           
            'Authorization': "Bearer " + self.token
        }
        response = requests.request("GET", tablesUrl, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            return None


