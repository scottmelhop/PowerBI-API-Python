from pbiapi import PowerBIAPIClient

if __name__ == "__main__":
    c = PowerBIAPIClient("a9ae5b54-3600-4917-a9dc-3020723360b3", "8a8b9df8-b6b4-4522-88f5-dbb9fe41ca68", "e86pd2ZpYypBMkMfzP5uJ/ZY/Oz0v3QOBoPtKz9z0ow=")
    c.rebind_report_in_workspace("forge-prod-test", "base_dataset", "base_report")