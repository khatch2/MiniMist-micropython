import network
import gc
import time
import esp

print('~~~ RUNNING:  boot.py')

net_details = {'ASUS-sbak': 'Gurubhavan1$',
               'Stockholms_stadsbibliotek': 'stockholm'}
ssid = 'Kocin'
password = 'kocin555'
host_name = 'minimist-thesis'


def scan_AP(wlan):
    # TODO: Can estable a dictonary to store know network details if one of the
    #       scan is available in the dictonary we use this ssid and corresponding password
    #       for the connect.
    wlan.active(True)
    authmodes = ['Open', 'WEP', 'WPA-PSK' 'WPA2-PSK4', 'WPA/WPA2-PSK']
    for (ssid, bssid, channel, RSSI, authmode, hidden) in wlan.scan():
        print("* {:s}".format(ssid))
        print(
            "   - Auth: {} {}".format(authmodes[authmode], '(hidden)' if hidden else ''))
        print("   - Channel: {}".format(channel))
        print("   - RSSI: {}".format(RSSI))
        print(
            b"   - BSSID: {:02x}:{:02x}:{:02x}:{:02x}:{:02x}:{:02x}".format(*bssid))
        print()


def get_network_info(station):
    print("\n[*] Network information for SSID: ", ssid,
          "\n  [+] ESP32 IP Addr: ", station.ifconfig()[0],
          "\n  [+] ESP32 Hostname : ", station.config('dhcp_hostname'),
          "\n  [+] Subnet Mask : ", station.ifconfig()[1],
          "\n  [+] Gateway IP : ", station.ifconfig()[2],
          "\n  [+] DNS : ", station.ifconfig()[3])


def connect_wifi():
    gc.collect()
    station = network.WLAN(network.STA_IF)
    #scan_AP(station)
    if not station.isconnected():
        print('[*] Connecting to WIFI ')
        station.active(True)
        print('[+] Active set true')
        station.config(dhcp_hostname=host_name)
        print('[+] DHCP-Hostname set.')
        station.connect(ssid, password)
        print('[+] Connecting to SSID ')
        startTime = time.ticks_ms()
        while not station.isconnected():
            if (time.ticks_ms() - startTime > 10000):
                station.disconnect()
                print("\n  Cound't connect to local Wifi network. Check Wifi credentials and Wifi Network status.")
                return
            else:
                time.sleep(0.250)
                print(".", end = "")
        print(" Connection Successful \n")
    else:
        print(" Already Connected")
    get_network_info(station)


connect_wifi()

