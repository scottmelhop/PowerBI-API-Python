import argparse
import json
import os
from pathlib import Path

from requests.exceptions import HTTPError

from pbiapi import PowerBIAPIClient

azure_tenant_id = os.environ.get("AZURE_TENANT_ID")
azure_client_id = os.environ.get("AZURE_CLIENT_ID")
azure_client_secret = os.environ.get("AZURE_CLIENT_SECRET")


# def setDBConnection(pbi_client, ws, ):


def main():
    pbi_client = PowerBIAPIClient(azure_tenant_id, azure_client_id, azure_client_secret,)
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace_name", dest="workspace_name", help="workspace name")
    parser.add_argument("--ds_name", dest="ds_name", help="ds_name")
    parser.add_argument("--username", dest="username", help="db username")
    parser.add_argument("--password", dest="password", help="db password")
    args = parser.parse_args()
    print(args)
    pbi_client.take_over_dataset(args.workspace_name, args.ds_name)
    gw_id = pbi_client.get_dataset_datasources_by_name(args.workspace_name, args.ds_name)
    gatewayId = gw_id[0]["gatewayId"]
    datasourceId = gw_id[0]["datasourceId"]
    pbi_client.update_datasource(gatewayId, datasourceId, user_name=args.username, password=args.password)


if __name__ == "__main__":
    main()
