import subprocess
import json
from tabulate import tabulate
from AzureRetailPricesApi import AzureRetailPricesClient

DEBUG=None

# Helper to run az cli and get disk details
def get_disk_details(disk_name, resource_group, subscription):
    cmd = [
        "az", "disk", "show",
        "--name", disk_name,
        "--resource-group", resource_group,
        "--subscription", subscription,
        "--output", "json"
    ]
    if DEBUG:
        print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        if DEBUG:
            print(f"[ERROR] Failed to get disk details: {result.stderr}")
        else:
            raise Exception(f"Failed to get disk details: {result.stderr}")
    if DEBUG:
        print(f"[DEBUG] Disk details for {disk_name}: {result.stdout}")
    return json.loads(result.stdout)

# Convert USD to GBP
def convert_usd_to_gbp(value):
    return float(value) * 0.75

# Use AzureRetailPricesClient for all pricing queries
api_client = AzureRetailPricesClient()
def get_disk_price(sku, size_gb, product_name, region="uksouth"):
    if '_' in sku:
        tier, redundancy = sku.split('_', 1)
        formatted_sku = f"{tier} {redundancy}"
    else:
        formatted_sku = sku

    if DEBUG:
        print(f"[INFO] Querying AzureRetailPricesClient for SKU '{formatted_sku}', region '{region}', productName='{product_name}'")
    query_args = {
        'armRegionName': region,
        'skuName': formatted_sku,
        'productName': product_name
    }
    if product_name:
        query_args['productName'] = product_name
    if DEBUG:
        print(f"[QUERY] api_client.query({query_args})")
    results = api_client.query(**query_args)
    if DEBUG:
        print(f"results are '{results}'")
    if not results:
        return None
    # Filter for the Disk meter name and return its retailPrice
    target_meter_name = f"{formatted_sku} Disk"
    if DEBUG:
        print(f"target meter name is '{target_meter_name}'")
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict):
                meter_name = item.get("meterName") or item.get("meter_name")
                if meter_name == target_meter_name:
                    price_usd = item.get("retailPrice")
                    if price_usd is not None:
                        return convert_usd_to_gbp(price_usd)
    elif isinstance(results, dict):
        meter_name = results.get("meterName") or results.get("meter_name")
        if meter_name == target_meter_name:
            price_usd = results.get("retailPrice")
            if price_usd is not None:
                return convert_usd_to_gbp(price_usd)
    return None

def get_premiumv2_price(region, size_gb, iops, throughput, tierMinimumUnits=None):
    product_name = "Azure Premium SSD v2"
    sku_name = "Premium LRS"
    total = 0.0
    breakdown = {}
    # 1. Provisioned Capacity (no tierMinimumUnits)
    cap_args = {
        'armRegionName': region,
        'skuName': sku_name,
        'productName': product_name
    }
    if DEBUG:
        print(f"[QUERY] api_client.query({cap_args}) for Premium SSD v2 Provisioned Capacity")
    results = api_client.query(**cap_args)
    if isinstance(results, str):
        try:
            results = json.loads(results)
        except Exception:
            print("[ERROR] Could not parse API result string.")
            return None
    if not isinstance(results, list):
        print("[ERROR] Unexpected API result format.")
        return None
    for item in results:
        if item.get("type") != "Consumption":
            continue
        meter = item.get("meterName", "")
        if "Provisioned Capacity" in meter:
            price_usd = float(item.get("retailPrice", 0.0))
            price = convert_usd_to_gbp(price_usd)
            cost = float(price) * float(size_gb) * 730.0
            breakdown['capacity'] = cost
            total += cost
            if DEBUG:
                print(f"[INFO] Capacity: {price_usd:.6f} USD, {price:.6f} GBP * {float(size_gb):.2f} * 730 = {cost:.6f} GBP")
    # 2. Provisioned IOPS (no tierMinimumUnits, but must check against throughput tierMinimumUnits)
    if DEBUG:
        print(f"[QUERY] api_client.query({cap_args}) for Premium SSD v2 Provisioned IOPS")
    results = api_client.query(**cap_args)
    if isinstance(results, str):
        try:
            results = json.loads(results)
        except Exception:
            print("[ERROR] Could not parse API result string.")
            return None
    if not isinstance(results, list):
        print("[ERROR] Unexpected API result format.")
        return None
    # Set the tierMinimumUnits for IOPS
    iops_tier_min = 3000.0
    for item in results:
        if item.get("type") != "Consumption":
            continue
        meter = item.get("meterName", "")
        if "Provisioned IOPS" in meter:
            price_usd = float(item.get("retailPrice", 0.0))
            price = convert_usd_to_gbp(price_usd)
            if float(iops) <= iops_tier_min:
                cost = 0.0
                if DEBUG:
                    print(f"[INFO] IOPS: {float(iops):.2f} <= {iops_tier_min} (tierMinimumUnits), cost is 0.0 GBP")
            else:
                cost = float(price) * (float(iops) - iops_tier_min) * 730.0
                if DEBUG:
                    print(f"[INFO] IOPS: {price_usd:.6f} USD, {price:.6f} GBP * ({float(iops):.2f} - {iops_tier_min}) * 730 = {cost:.6f} GBP")
            breakdown['iops'] = cost
            total += cost
    # 3. Provisioned Throughput (with tierMinimumUnits)
    throughput_args = {
        'armRegionName': region,
        'skuName': sku_name,
        'productName': product_name,
        'tierMinimumUnits': 125.0
    }
    if DEBUG:
        print(f"[QUERY] api_client.query({throughput_args}) for Premium SSD v2 Provisioned Throughput")
    results = api_client.query(**throughput_args)
    if isinstance(results, str):
        try:
            results = json.loads(results)
        except Exception:
            print("[ERROR] Could not parse API result string.")
            return None
    if not isinstance(results, list):
        print("[ERROR] Unexpected API result format.")
        return None
    for item in results:
        if item.get("type") != "Consumption":
            continue
        meter = item.get("meterName", "")
        if "Provisioned Throughput" in meter:
            price_usd = float(item.get("retailPrice", 0.0))
            price = convert_usd_to_gbp(price_usd)
            throughput_tier_min = 125.0
            if float(throughput) <= throughput_tier_min:
                cost = 0.0
                if DEBUG:
                    print(f"[INFO] Throughput: {float(throughput):.2f} <= {throughput_tier_min} (tierMinimumUnits), cost is 0.0 GBP")
            else:
                cost = float(price) * (float(throughput) - throughput_tier_min) * 730.0
                if DEBUG:
                    print(f"[INFO] Throughput: {price_usd:.6f} USD, {price:.6f} GBP * ({float(throughput):.2f} - {throughput_tier_min}) * 730 = {cost:.6f} GBP")
            breakdown['throughput'] = cost
            total += cost
    if not breakdown:
        print(f"[WARN] No Premium SSD v2 price components found for region {region}")
        return None
    if DEBUG:
        print(f"[INFO] Premium SSD v2 price breakdown: {breakdown}, total: {total}")
    return total
    
def get_standardssd_tier(size_gb):
    # Mapping based on Azure Standard SSD disk sizes (as of 2024)
    # https://learn.microsoft.com/en-us/azure/virtual-machines/disks-types#standard-ssd
    # This can be extended as needed
    size_to_tier = [
        (4, "E1"),
        (8, "E2"),
        (16, "E3"),
        (32, "E4"),
        (64, "E6"),
        (128, "E10"),
        (256, "E15"), 
        (512, "E20"),
        (1024, "E30"),
        (2048, "E40"),
        (4096, "E50"),
        (8192, "E60"),
        (16384, "E70"),
        (32767, "E80"),
    ]
    for max_size, tier in size_to_tier:
        if size_gb <= max_size:
            return tier
    return f"E{size_gb}"  # fallback

def get_premiumssd_tier(size_gb):
    # Mapping based on Azure Standard SSD disk sizes (as of 2024)
    # https://learn.microsoft.com/en-us/azure/virtual-machines/disks-types#standard-ssd
    # This can be extended as needed
    size_to_tier = [
        (4, "P1"),
        (8, "P2"),
        (16, "P3"),
        (32, "P4"),
        (64, "P6"),
        (128, "P10"),
        (256, "P15"), 
        (512, "P20"),
        (1024, "P30"),
        (2048, "P40"),
        (4096, "P50"),
        (8192, "P60"),
        (16384, "P70"),
        (32767, "P80"),
    ]
    for max_size, tier in size_to_tier:
        if size_gb <= max_size:
            return tier
    return f"P{size_gb}"  # fallback

# Main logic
def main():
    # Read disks from disks.json and take the first five
    with open("disks.json") as f:
        all_disks = json.load(f)
    disks = all_disks
    table = []
    for idx, disk in enumerate(disks, 1):
        # Support both 'diskname'/'resourcegroup' and 'name'/'resource_group' keys
        disk_name = disk.get("diskname") or disk.get("name")
        resource_group = disk.get("resourcegroup") or disk.get("resourceGroup")
        subscription = disk.get("subscription") or disk.get("subscriptionId")
        if DEBUG:
            print(f"\n[INFO] Processing disk {idx}: {disk_name} in resource group {resource_group}")
        try:
            details = get_disk_details(disk_name, resource_group, subscription)
        except Exception as e:
            if DEBUG:
                print(f"[WARN] Disk '{disk_name}' in resource group '{resource_group}' not found or error occurred: {e}. Marking as N/A.")
            # Output all columns as N/A for this disk
            table.append([
                disk_name or "N/A",
                "N/A",  # Size (GB)
                "N/A",  # SKU
                "N/A",  # IOPS
                "N/A",  # Throughput (MBps)
                "N/A",  # Existing Price
                "N/A",  # Standard Price
                "N/A"   # PremiumV2 Price
            ])
            continue
        if DEBUG:
            print(f"[DEBUG] Disk details: {details}")
        size_gb = details["diskSizeGB"]
        sku = details["sku"]["name"]
        # Example: 'Premium_LRS' or 'StandardSSD_LRS'
        if '_' in sku:
            tier, redundancy = sku.split('_', 1)
            # Infer the performance tier if not explicitly set
            disk_tier = details.get("tier")
            if not disk_tier or disk_tier == "?":
                if tier == "Premium":
                    disk_tier = get_premiumssd_tier(size_gb)
                elif tier == "StandardSSD":
                    disk_tier = get_standardssd_tier(size_gb)
                else:
                    disk_tier = tier  # fallback
            if tier == "Premium":
                existing_sku = f"{disk_tier} {redundancy}"
            else:
                existing_sku = f"{tier} {redundancy}"
            # Standard SSD logic: get correct tier for size
            standardssd_tier = get_standardssd_tier(size_gb)
            premiumssd_tier = get_premiumssd_tier(size_gb)
            standard_sku = f"{standardssd_tier} {redundancy}"
            premium_sku = f"{premiumssd_tier} {redundancy}"
        iops = details.get("diskIOPSReadWrite", "?")
        throughput = details.get("diskMBpsReadWrite", "?")
        if DEBUG:
            print(f"will search prices for '{existing_sku}'")
        if tier == "Premium":
            product_name = "Premium SSD Managed Disks"
        else:
            product_name = "Standard SSD Managed Disks"

        # Get prices using correct formatted SKUs
        if DEBUG:
            print(f"Get existing price")
        existing_price = get_disk_price(existing_sku, size_gb, product_name)
        # For Standard SSD, set productName and use correct skuName
        if DEBUG:
            print(f"Get standard price")
        standard_price = get_disk_price(standard_sku, size_gb, "Standard SSD Managed Disks")
        if DEBUG:
            print(f"Get premiumv2 price")
        premiumv2_price = get_premiumv2_price("uksouth", size_gb, iops, throughput)
        if DEBUG:
            print(f"Existing price is '{existing_price}'")
        if existing_price is None:
            print(f"[WARN] No existing price found for {disk_name} ({existing_sku})")
        if standard_price is None:
            print(f"[WARN] No StandardSSD price found for {disk_name}")
        if premiumv2_price is None:
            print(f"[WARN] No PremiumV2 price found for {disk_name}")
        # Format prices for table output with 6 decimal places
        def fmt(val):
            if isinstance(val, float):
                return f"{val:.6f}"
            return val
        table.append([
            disk_name, size_gb, sku, iops, throughput, fmt(existing_price), fmt(standard_price), fmt(premiumv2_price)
        ])
    print("\n[RESULT] Disk Price Comparison Table:")
    print(tabulate(table, headers=["Disk_Name", "Size_GB", "SKU", "IOPS", "Throughput_MBps", "Existing_Price", "Standard_Price", "PremiumV2_Price"]))

if __name__ == "__main__":
    main()
