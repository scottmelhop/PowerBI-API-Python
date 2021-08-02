from pbiapi import PowerBIAPIClient
import os
import argparse
from pathlib import Path
from requests.exceptions import HTTPError
import json
azure_tenant_id=os.environ.get('AZURE_TENANT_ID')
azure_client_id=os.environ.get('AZURE_CLIENT_ID')
azure_client_secret=os.environ.get('AZURE_CLIENT_SECRET')


#def setDBConnection(pbi_client, ws, ):

def main():
    pbi_client = PowerBIAPIClient(
        azure_tenant_id,
        azure_client_id,
        azure_client_secret,
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace_name",dest="workspace_name", help="the workspace_name", required=True)
    parser.add_argument("--report_id",dest="report_id", help="the report_id to be cloned", required=True)
    parser.add_argument("--new_report_name",dest="new_report_name", help="The new report name", required=True)
    args =parser.parse_args()
    print(args)
    print(pbi_client.get_reports_in_workspace('parralel_run_production'))   
    print(pbi_client.clone_report_by_id(args.workspace_name, args.report_id, args.new_report_name) )
 
if __name__ == "__main__":
    main()

