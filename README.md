# PowerBI-API-Python
This python package consists of helper functions for working with the Power BI API. To use this first make sure you have a Service Principal set up in Azure that has access to Power BI API. This [guide](https://cognitedata.atlassian.net/wiki/spaces/FORGE/pages/1003814928/Power+BI+API+Set+Up) shows how to set up a SP App.

## Basic Usage
The package can be installed by using the wheel in the `dist` folder. Import the package by running:

```python
from pbiapi import PowerBiApiClient
```

Initiate the client by running: 

