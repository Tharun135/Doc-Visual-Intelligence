from analyzers.visual_detector import detect_existing_visual_assets, detect_visuals

content = """To configure the EtherNet/IP IO Connector in IIH Essentials, proceed as follows:

1. Open the \"IE Devices\" window in IEM and select the IE Device where the EtherNet/IP IO Connector is running.

    ![iem-ied-device](../media/iih-essential-config-1.png)

2. Open the \"IIH Essential\" from the installed apps.

    ![iih-essential-app](../media/iih-essential-config-2.png)

3. Add an asset for the PLC to receive data.

    ![iih-essential-add-asset](../media/iih-essential-config-3.png)

4. Drag and drop the tags on the \"Attributes\" tab to associate it with the asset.

    ![iih-essential-config-attribute](../media/iih-essential-config-4.png)

    !!! info \"NOTICE\"
        For optimal performance, it is recommended to always subscribe (add to Asset) to all data points from each PLC that have been configured in Model Maker.

The EtherNet/IP IO Connector is now configured, with the asset created and tags linked to it.
"""

print("assets=", detect_existing_visual_assets(content))
recs = detect_visuals("Configuring the EtherNet/IP IO Connector", content)
print([(r["visual_type"], r["confidence"], r.get("existing_count"), r.get("gap_message")) for r in recs])
