# PowerBI-API-Python
This python package consists of helper functions for working with the Power BI API. To use this first make sure you have a Service Principal set up in Azure that has access to Power BI API. This [guide](https://cognitedata.atlassian.net/wiki/spaces/FORGE/pages/1003814928/Power+BI+API+Set+Up) shows how to set up a SP App.

## Basic Usage

Install using pip
```python
pip install pbiapi
```

Add the client to your project with:

```python
from pbiapi import PowerBiApiClient
```

Initiate the client by running: 
```python
pbi_client = PowerBiApiClient( 
    <Tenant Id>,
    <Application Id>,
    <Service Principal Secret>
    )
```

You can then get all the workspaces the Service Principal is admin of by running:
```python
pbi_client.getWorkspaces()
pbi_client.workspaces
```

