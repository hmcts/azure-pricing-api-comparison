from AzureRetailPricesApi import AzureRetailPricesClient
api = AzureRetailPricesClient()
data = api.query(productName='Azure Premium SSD v2', armRegionName='uksouth', meterName='Premium LRS Provisioned Throughput (MBps)', tierMinimumUnits=125.0)
print(data)