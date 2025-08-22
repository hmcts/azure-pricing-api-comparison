import subprocess
import json
import time
import os
from tabulate import tabulate
from AzureRetailPricesApi import AzureRetailPricesClient

DEBUG = None
RESULTS_FILE = "results/blob_price_results.json"
MAX_RETRIES = 3
RETRY_DELAY = 10  # seconds

def save_progress(table):
    with open(RESULTS_FILE, "w") as f:
        json.dump(table, f)

def load_progress():
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            return json.load(f)
    return []

def row_key(row):
    # Use account name and resource group as unique key
    return f"{row[0]}|{row[1]}"

def retry_api_call(func, *args, **kwargs):
    for attempt in range(1, MAX_RETRIES + 1):
        result = func(*args, **kwargs)
        if result is not None:
            return result
        if DEBUG:
            print(f"[RETRY] API call failed (attempt {attempt}/{MAX_RETRIES}), retrying in {RETRY_DELAY}s...")
        time.sleep(RETRY_DELAY)
    return None

def get_storage_account_details(account_name, resource_group, subscription):
    cmd = [
        "az", "storage", "account", "show",
        "--name", account_name,
        "--resource-group", resource_group,
        "--subscription", subscription,
        "--output", "json"
    ]
    if DEBUG:
        print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        if DEBUG:
            print(f"[WARN] Could not fetch details for {account_name}: {result.stderr}")
        return None
    return json.loads(result.stdout)

def get_blob_price(account_name, resource_group, subscription, region, redundancy, kind):
    # Get current capacity (in GB) using az monitor metrics list
    cmd = [
        "az", "monitor", "metrics", "list",
        "--resource", f"/subscriptions/{subscription}/resourceGroups/{resource_group}/providers/Microsoft.Storage/storageAccounts/{account_name}",
        "--metric", "UsedCapacity",
        "--interval", "PT1H",
        "--aggregation", "Average",
        "--output", "json"
    ]
    if DEBUG:
        print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        if DEBUG:
            print(f"[WARN] Could not fetch metrics for {account_name}: {result.stderr}")
        return None
    metrics = json.loads(result.stdout)
    usage_gb = 1000  # default fallback
    try:
        data = metrics["value"][0]["timeseries"][0]["data"]
        # Get the latest non-null average value
        for point in reversed(data):
            avg = point.get("average")
            if avg is not None:
                usage_gb = float(avg) / (1024 ** 3)  # Convert bytes to GB
                break
    except Exception as e:
        if DEBUG:
            print(f"[WARN] Could not parse metrics: {e}")
        # fallback to default

    api_client = AzureRetailPricesClient()
    kind_map = {
        "Storage": "General Block Blob",
        "StorageV2": "General Block Blob v2",
        "BlockBlobStorage": "Premium Block Blob"
    }
    product_name = kind_map.get(kind, kind)
    redundancy_prefix = redundancy.split('_')[0]
    redundancy_suffix = redundancy.split('_')[-1]
    if DEBUG:
        print(f"Redundancy is '{redundancy}")
    if kind == "BlockBlobStorage":
        sku_name = f"Premium {redundancy_suffix}"
        meter_name = f"Premium {redundancy_suffix} Data Stored"
    elif kind == "Storage":
        sku_name = f"Standard {redundancy_suffix}"
        meter_name = f"{redundancy_suffix} Data Stored"
    elif kind == "StorageV2":
        sku_name = f"Hot {redundancy_suffix}"
        meter_name = f"Hot {redundancy_suffix} Data Stored"
    else:
        sku_name = f"{redundancy_prefix} {redundancy_suffix}"
        meter_name = f"{redundancy_prefix} {redundancy_suffix} Data Stored"

    query_args = {
        'armRegionName': region,
        'productName': product_name,
        'skuName': sku_name,
        'meterName': meter_name
    }
    if DEBUG:
        print(f"[QUERY] api_client.query({query_args})")
    results = retry_api_call(api_client.query, **query_args)
    if DEBUG:
        print(f"API response is '{results}")
    if not results:
        return None
    price_per_gb = None
    for item in results:
        meter = item.get("meterName", "")
        if "Data Stored" in meter:
            price_per_gb = float(item.get("retailPrice", 0.0))
            break
    if price_per_gb is None:
        return None
    gbp = price_per_gb * 0.75 * usage_gb
    return gbp

def main():
    # Read blobs.json
    with open("blobs.json") as f:
        accounts = json.load(f)
    table = load_progress()
    processed_keys = set(row_key(row) for row in table)
    for acc in accounts:
        name = acc["storageAccountName"]
        rg = acc["resourcegroup"]
        sub = acc["subscription"]
        key = f"{name}|{rg}"
        if key in processed_keys:
            if DEBUG:
                print(f"[SKIP] Already processed {name} in {rg}")
            continue
        details = retry_api_call(get_storage_account_details, name, rg, sub)
        if not details:
            row = [name, rg, "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"]
            table.append(row)
            save_progress(table)
            continue
        kind = details.get("kind", "?")
        actual_redundancy = details.get("sku", {}).get("name", "?")
        region = details.get("location", "uksouth")
        # For pricing, always use ZRS if not already ZRS
        redundancy_for_pricing = actual_redundancy
        if not actual_redundancy.endswith("ZRS"):
            redundancy_for_pricing = actual_redundancy.split('_')[0] + "_ZRS"
            if DEBUG:
                print(f"[INFO] Overriding redundancy for pricing to {redundancy_for_pricing}")
        price_v1 = retry_api_call(get_blob_price, name, rg, sub, region, redundancy_for_pricing, kind="Storage")
        price_block = retry_api_call(get_blob_price, name, rg, sub, region, redundancy_for_pricing, kind="BlockBlobStorage")
        price_v2 = retry_api_call(get_blob_price, name, rg, sub, region, redundancy_for_pricing, kind="StorageV2")
        row = [
            name, rg, kind, actual_redundancy, region,
            f"{price_v1:.2f}" if price_v1 is not None else "N/A",
            f"{price_block:.2f}" if price_block is not None else "N/A",
            f"{price_v2:.2f}" if price_v2 is not None else "N/A"
        ]
        table.append(row)
        save_progress(table)
    print("\n[RESULT] Blob Storage Price Comparison Table (for 1TB Hot Data):")
    print(tabulate(table, headers=["Account_Name", "Resource_Group", "Kind", "Redundancy", "Region", "Storage_V1_(GBP)", "BlockBlob_(GBP)", "Storage_V2_(GBP)"]))

if __name__ == "__main__":
    main()