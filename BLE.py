import asyncio
from bleak import BleakClient, BleakScanner

UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

async def main():
    print("Scanning for Nano33BLE...")

    devices = await BleakScanner.discover()
    for d in devices:
        print(f"Name: {d.name}, Address: {d.address}")

    nano = next((d for d in devices if d.name and "Nano33BLE" in d.name), None)


    if not nano:
        print("Nano 33 BLE not found.")
        return

    async with BleakClient(nano.address) as client:
        print(f"Connected to {nano.name}")

        def handle_notification(sender, data):
            print("Arduino:", data.decode())

        await client.start_notify(TX_CHAR_UUID, handle_notification)

        # Send ON command
        await client.write_gatt_char(RX_CHAR_UUID, b"TEST\0")
       # await asyncio.sleep(2)

        await client.stop_notify(TX_CHAR_UUID)

        while True:
            command = input("Arduino Command (BUZZER/CHANGE/END/exit): ")


            # await client.stop_notify(TX_CHAR_UUID)

            if command != 'exit':
                command = command + "\0"
                await client.write_gatt_char(RX_CHAR_UUID, command.encode('utf-8'))
            else :
                command = command + "\0"
                await client.write_gatt_char(RX_CHAR_UUID, command.encode('utf-8'))
                exit()



asyncio.run(main())
