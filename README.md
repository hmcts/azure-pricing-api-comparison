# Azure SKU Comparison Toolkit

This toolkit helps you compare Azure SKUs and their monthly prices (in GBP) for various Azure resources, such as managed disks and blob storage accounts. It is designed to be extensible for other Azure resource types.

## Features
- Compare SKUs and pricing for Azure resources (currently supports Disks and Blob Storage)
- Reads resource details from JSON files (e.g., `disks.json`, `blobs.json`)
- Fetches live resource info from Azure using the Azure CLI
- Looks up prices using the Azure Retail Prices API
- Handles missing resources gracefully (outputs N/A)
- Infers performance tiers or redundancy if not explicitly set
- Outputs a comparison table with key properties and prices for each resource
- Supports debug mode for verbose output
- Resilient to API rate limits (retries and resumes progress)

## Requirements
- Python 3.7+
- Azure CLI (`az`) installed and logged in
- Required Python packages: `tabulate`, and your custom `AzureRetailPricesApi.py`

## Setup
1. Clone this repository.
2. Create a virtual environment:
      ```sh
      python3 -m venv .venv
      source .venv/bin/activate
      ```
3. Install dependencies:
      ```sh
      pip install tabulate
      ```
4. Ensure you have the Azure CLI installed and are logged in:
      ```sh
      az login
      ```
5. Prepare a resource input file (e.g., `disks.json` or `blobs.json`) in the repo root. Example formats:
      - For disks:
         ```json
         [
            {"diskname": "myDisk1", "resourcegroup": "myResourceGroup1", "subscription": "mySubscription1"},
            {"diskname": "myDisk2", "resourcegroup": "myResourceGroup2", "subscription": "mySubscription1"}
         ]
         ```
      - For blob storage:
         ```json
         [
            {"storageAccountName": "saName", "resourcegroup": "rgName", "subscription": "subName"}
         ]
         ```

   You can retrieve the data you need using the following commands.

   For storage accounts:

   ```
   az graph query -q "Resources | where type == 'microsoft.storage/storageaccounts' | where sku.name in ('Premium_LRS', 'Premium_ZRS', 'Standard_GRS', 'Standard_RAGRS') | project name, resourceGroup, subscriptionId, sku.name" --first 1000 -o json | jq '.data' > blobs.json
   ```

   For disks:

   ```
   az graph query -q "Resources | where type == 'microsoft.compute/disks' | where sku.name in ('Premium_LRS', 'Premium_ZRS', 'Standard_GRS', 'Standard_RAGRS') | project name, resourceGroup, subscriptionId, sku.name" --first 1000 -o json | jq '.data' > disks.json
   ```


## Usage
Run the relevant script for your resource type:

- For disks:
   ```sh
   python compare_disk_prices.py
   ```
- For blob storage:
   ```sh
   python compare_blob_prices.py
   ```

- Set `DEBUG=True` in the script for verbose output.
- The output is a table comparing key properties and prices for each resource and SKU type.

Example output for disks:
```
Disk_Name    Size_GB    SKU          IOPS    Throughput_MBps    Existing_Price    Standard_Price    PremiumV2_Price
-----------  ---------  -----------  ------  -----------------  ----------------  ----------------  -----------------
DISK-NAME-01 1000       Premium_LRS  5000    200                122.66            63.36             80.88
```

Example output for blob storage:
```
Account_Name      Resource_Group   Kind              Redundancy   Region   Storage_V1_(GBP)   BlockBlob_(GBP)   Storage_V2_(GBP)
----------------  --------------  ----------------  -----------  -------  -----------------  ----------------  ----------------
saName            rgName           StorageV2         Standard_LRS uksouth  12.34              15.67             10.89
```

## Notes
- If a resource is not found in Azure, the script will output a row with `N/A` for all columns.
- For disks and blob storage, the tool will infer the performance tier or redundancy if it is not set in Azure.
- Prices are converted from USD to GBP using a fixed rate (0.75).
- Blob storage pricing, the script is currently coded to use the ZRS redundancy type by default.
- Progress is saved after each resource, so the script can resume if interrupted.

## Extending
You can extend this toolkit to support other Azure resource types by following the patterns in the provided scripts and using the AzureRetailPricesApi client.

## Acknowledgements

The `AzureRetailPricesApi.py` was copied from https://github.com/holgerjs/query-the-azure-retail-prices-api/tree/main and altered to enable retrieval of Premium V2 SSD Managed Disk pricing that accounts for the free usage allowed by Microsoft.
