# PowerBI-API-Python
This python package consists of helper functions for working with the Power BI API. To use this first make sure you have a Service Principal set up in Azure that has access to Power BI API. This [guide](https://cognitedata.atlassian.net/wiki/spaces/FORGE/pages/1003814928/Power+BI+API+Set+Up) shows how to set up a SP App.

## Basic Usage

Install using pip
```sh
pip install pbiapi
```

Add the client to your project with:

```python
from pbiapi import PowerBIAPIClient
```

Initiate the client by running:
```python
pbi_client = PowerBIAPIClient(
    <Tenant Id>,
    <Application Id>,
    <Service Principal Secret>,
)
```

You can then get all the workspaces the Service Principal is admin of by running:
```python
pbi_client.get_workspaces()
```

in order to install the whl package:
cd dist
pip install pbiapi-0.2.3-py3-none-any.whl

within python driver:
workspace_name='the_name_of_the_workspace'
report_id='97e4b697-8223-4cfa-b29c.......'
new_report_name='new_report_name'
print(pbi_client.clone_report_by_id(workspace_name, report_id, new_report_name=new_report_name) )
