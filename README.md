# Azure Disk SKU & Price Comparison Tool

This tool helps you compare Azure managed disk SKUs and their monthly prices (in GBP) for a list of disks in your Azure subscription. It supports Standard SSD, Premium SSD, and Premium SSD v2, and can infer disk performance tiers based on SKU and size.

## Features
- Reads disk details from a `disks.json` file
- Fetches disk info from Azure using the Azure CLI
- Looks up prices using the Azure Retail Prices API
- Handles missing disks gracefully (outputs N/A)
- Infers performance tier if not explicitly set
- Outputs a comparison table with size, SKU, IOPS, throughput, and prices for each disk
- Supports debug mode for verbose output

## Requirements
- Python 3.7+
- Azure CLI (`az`) installed and logged in
- Required Python packages: `tabulate`, and your custom `AzureRetailPricesApi.py`

## Setup
1. Clone this repository.
2. Create a virtual environment:
    ```
    python3 -m venv .venv
    source .venv/bin/activate
3. Install dependencies:
   ```sh
   pip install tabulate
   ```
4. Ensure you have the Azure CLI installed and are logged in:
   ```sh
   az login
   ```
5. Prepare a `disks.json` file in the repo root. Example format:
   ```json
   [
     {"diskname": "myDisk1", "resourcegroup": "myResourceGroup1", "subscription": "mySubscription1"},
     {"diskname": "myDisk2", "resourcegroup": "myResourceGroup2", "subscription": "mySubscription1"}
   ]
   ```

## Usage
Run the script:
```sh
python compare_disk_prices.py
```

- Set `DEBUG=True` in the script for verbose output.
- The output is a table comparing disk size, SKU, IOPS, throughput, and prices for each disk and SKU type.

```
Disk_Name                                            Size_GB    SKU          IOPS    Throughput_MBps    Existing_Price    Standard_Price    PremiumV2_Price
--------------------------------------------------  ---------  -----------  ------  -----------------  ----------------  ----------------  -----------------
DISK-NAME-01                                        1000       Premium_LRS  5000    200                122.661000        63.360000         80.879438
```

## Notes
- If a disk is not found in Azure, the script will output a row with `N/A` for all columns.
- For Premium and Standard SSD disks, the tool will infer the performance tier if it is not set in Azure.
- Prices are converted from USD to GBP using a fixed rate (0.75).

## Acknowledgements

The `AzureRetailPricesApi.py` was copied from https://github.com/holgerjs/query-the-azure-retail-prices-api/tree/main and altered to enable retrieval of Premium V2 SSD Managed Disk pricing that accounts for the free usage allowed by Microsoft.
