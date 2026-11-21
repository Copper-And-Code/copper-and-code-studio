# boot.py of a board with the Copper and Code settings: at power-on, connect to the best saved
# WiFi network in range, so that every app finds the network ready. Upload it with
# cac_settings.py to the root of the flash: / on the ESP32 and the RP2350, /flash on the STM32.
# Without a saved network in range it gives up after one scan, a couple of seconds.
try:
    import cac_settings

    cac_settings.connect()
except Exception as e:                     # the board must start all the same
    print("boot: WiFi not connected:", repr(e))
