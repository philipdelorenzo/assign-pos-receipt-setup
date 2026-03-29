import usb.core

# Find all connected USB devices
devices = usb.core.find(find_all=True)

for dev in devices:
    print(
        f"Device: {usb.util.get_string(dev, dev.iProduct) if dev.iProduct else 'Unknown'}"
    )
    print(f"  - Vendor ID: {hex(dev.idVendor)}")
    print(f"  - Product ID: {hex(dev.idProduct)}")
    print("-" * 20)
