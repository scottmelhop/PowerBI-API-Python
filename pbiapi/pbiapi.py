import requests
import json 
import datetime


# DECORATORS
def checkToken(method_to_decorate):
    def wrapper(self, *args):     
        #Check for valid token       
        if self.token == None or self.tokenExpiration < datetime.datetime.utcnow():            
            #Try to set token, skip if fails
            if self.setToken():
                return method_to_decorate(self, *args)
            else:
                pass
        else:
            return method_to_decorate(self, *args)
    return wrapper

class PowerBiApiClient:    

    def __init__(self,tenant_id,client_id,client_secret):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.url = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token".format(tenant_id=self.tenant_id)
        self.token = None
        self.tokenExpiration = None
        self.workspaces = None
        self.headers = None

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

        response = requests.post(self.url, data=payload, headers=headers)

        if response.status_code == 200:
            self.token = response.json()['access_token']
            self.tokenExpiration = datetime.datetime.utcnow() + datetime.timedelta(seconds=3600)  

            self.headers = {
                'Content-Type': "application/x-www-form-urlencoded",
                'Authorization': "Bearer " + self.token
            }           
            return True
        else:
            print(response.status_code)
            print(response.text)
            return False

   
    #-----WORKSPACE FUNCTIONS----- 
    @checkToken 
    def getWorkspaces(self):        
        url = "https://api.powerbi.com/v1.0/myorg/groups" 
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            self.workspaces = response.json()['value']
            return True
        else:
            return False
     
    def findWorkspaceIdByName(self,name):
        self.getWorkspaces()
        if self.workspaces != None:
            return next((item['id'] for item in self.workspaces if item["name"] == name),None)
        else:
            return None
    
    @checkToken
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

    #-----DATASET FUNCTIONS----- 
    @checkToken 
    def getDatasetsInWorkspace(self,workspace_id):
        datasets_url = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/datasets".format(groupId = workspace_id)            
        response = requests.get(datasets_url, headers=self.headers)
        if response.status_code == 200:
            return response.json()['value']
        else:
            return None
            
    def findDatasetIdByName(self,datasets,name):
        return next((item['id'] for item in datasets if item["name"] == name),None)
        
    @checkToken    
    def refreshDatasetById(self,workspace_id,dataset_id):
        dataset_refresh = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/datasets/{datasetId}/refreshes".format(
                    groupId = workspace_id, 
                    datasetId = dataset_id
            )
        payload = "notifyOption=NoNotification"
        response = requests.post(dataset_refresh, data=payload, headers=self.headers)

        if response.status_code == 202:
            return True
        else:
            print(response.status_code)
            print(response.text)
            return False
    
    @checkToken
    def createPushDataset(self,workspace_id,schema,retention_policy):
        pushTable = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/datasets?defaultRetentionPolicy={retentionPolicy}".format(
            groupId = workspace_id,
            retentionPolicy = retention_policy            
        )
        headers = {
            'Content-Type': "application/json",           
            'Authorization': "Bearer " + self.token
        }
        response = requests.post(pushTable, data=json.dumps(schema), headers=headers)

        if response.status_code == 201 or response.status_code == 202:
            return True
        else:
            print(response.status_code)
            print(response.text)
            return False
        
    @checkToken
    def deleteDataset(self,workspace_id,dataset_id):
        deleteUrl = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/datasets/{datasetId}".format(
            groupId = workspace_id,
            datasetId = dataset_id
        )
        response = requests.delete(deleteUrl,headers=self.headers)
        if response.status_code == 200:
            return True
        else:
            return False

    @checkToken
    def postRows(self,workspace_id,dataset_id,table_name,data):
        postRowsUrl = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/datasets/{datasetId}/tables/{tableName}/rows".format(
            groupId = workspace_id,
            datasetId = dataset_id,
            tableName = table_name
        )
        headers = {
            'Content-Type': "application/json",           
            'Authorization': "Bearer " + self.token
        }
   
        rowCount = len(data)
        rowCursor = 0

        while rowCursor < rowCount:
            tempCursor = 0
            if (rowCursor +  10000) < rowCount:
                tempCursor = rowCursor +  10000
            else:
                tempCursor = rowCount

            uploadData = json.dumps({'rows':data[rowCursor:tempCursor]})
            response = requests.post(postRowsUrl, data=uploadData, headers=headers)
            if response.status_code == 200:
                print('Added rows {start} to {finish}'.format(start=str(rowCursor),finish=str(tempCursor)))
            else:
                print(response.status_code)
                print(response.text)  
                retry = 1
                while retry < 6:
                    print("Retry attempt: {attempt}".format(attempt=str(retry)))
                    response = requests.post(postRowsUrl, data=uploadData, headers=headers)
                    if response.status_code == 200:
                        print('Added rows {start} to {finish}'.format(start=str(rowCursor),finish=str(tempCursor)))
                        break
                    else:
                        retry = retry + 1
                if retry > 5: 
                    print("Error trying to add rows, aborting")
                    break
                
                
            rowCursor = tempCursor   
        
    @checkToken
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
        response = requests.put(updateTableUrl, data=json.dumps(schema), headers=headers)
        print(response.status_code)
        print(response.text)
    
    @checkToken
    def getTables(self,workspace_id,dataset_id):
        tablesUrl = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/datasets/{datasetId}/tables".format(
            groupId = workspace_id,
            datasetId = dataset_id
        )
        response = requests.get(tablesUrl, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            return None

    @checkToken
    def truncateTable(self,workspace_id,dataset_id,table_name):
        truncateTableUrl = "https://api.powerbi.com/v1.0/myorg/groups/{groupId}/datasets/{datasetId}/tables/{tableName}/rows".format(
            groupId = workspace_id,
            datasetId = dataset_id,
            tableName = table_name
        )

        response = requests.delete(truncateTableUrl,headers=self.headers)

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


                
        

        

