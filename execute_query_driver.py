import argparse
import os
from pathlib import Path

from requests.exceptions import HTTPError

from pbiapi import PowerBIAPIClient

azure_tenant_id = os.environ.get("AZURE_TENANT_ID")
azure_client_id = os.environ.get("AZURE_CLIENT_ID")
azure_client_secret = os.environ.get("AZURE_CLIENT_SECRET")


def main():
    pbi_client = PowerBIAPIClient(azure_tenant_id, azure_client_id, azure_client_secret,)
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace_name", dest="workspace_name", help="workspace name")
    parser.add_argument("--ds_name", dest="ds_name", help="ds_name")
    parser.add_argument("--query", dest="query", help="dax query")
    args = parser.parse_args()
    print(args)
    query = {}
    query["query"] = args.query
    queries = []
    queries.append(query)
    serializerSettings = {}
    serializerSettings["includeNulls"] = "true"
    res = pbi_client.execute_queries_by_name(
        workspace_name=args.workspace_name,
        dataset_name=args.ds_name,
        query_list=queries,
        serializerSettings=serializerSettings,
    )

    print(res)


if __name__ == "__main__":
    main()
