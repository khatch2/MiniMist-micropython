import machine
import time
import socket
import dht
import camera
import esp32
import buzzer
import gc
import json
import network
import sys

try:
    import uasyncio as asyncio
except:
    upip.install('micropython-uasyncio')
    upip.install('micropython-pkg_resources')
    import uasyncio as asyncio

import esp
esp.osdebug(None)

# Configure Indicator Leds
led1 = machine.Pin(12, machine.Pin.OUT)
led2 = machine.Pin(2, machine.Pin.OUT)
led3 = machine.Pin(15, machine.Pin.OUT)

# Assign Pin numbers allocated for reading Solar Panel, Battery and DHT11
solarvolt = machine.ADC(machine.Pin(32))
battvolt = machine.ADC(machine.Pin(33))
sensordht = dht.DHT11(machine.Pin(13))

BATTERY_MIN_ADC = 1.5 * 3
BATTERY_MAX_ADC = 0.9 * 3
# Set Attenuation to Full 3.3V on Pins that read voltage
solarvolt.atten(machine.ADC.ATTN_11DB)
battvolt.atten(machine.ADC.ATTN_11DB)

# Set Resolution to Full range 0 - 4095 on Pins that read voltage
solarvolt.width(machine.ADC.WIDTH_12BIT)
battvolt.width(machine.ADC.WIDTH_12BIT)

# Network Setting and WIFI setup

ssid = 'Kocin'
password = 'kocin555'
host_name = 'minimist-thesis'
ipaddr = ""

# Camera buffer to Reset if failed continuesly
camera_false_count = 0

def scan_AP(wlan):
    # TODO: Can estable a dictonary to store know network details if one of the
    #       scan is available in the dictonary we use this ssid and corresponding password
    #       for the connect.
    wlan.active(True)
    authmodes = ['Open', 'WEP', 'WPA-PSK' 'WPA2-PSK4', 'WPA/WPA2-PSK']
    for (ssid, bssid, channel, RSSI, authmode, hidden) in wlan.scan():
        print("* {:s}".format(ssid))
        print("   - Auth: {} {}".format(authmodes[authmode], '(hidden)' if hidden else ''))
        print("   - Channel: {}".format(channel))
        print("   - RSSI: {}".format(RSSI))
        print(b"   - BSSID: {:02x}:{:02x}:{:02x}:{:02x}:{:02x}:{:02x}".format(*bssid))
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
                buzzer.notify3()
                sys.exit()
                return
            else:
                time.sleep(0.250)
                print(".", end = "")
        print(" Connection Successful \n")
    else:
        print(" Already Connected")
    ipaddr = str(station.ifconfig()[0])
    get_network_info(station)


def init_cam():
    """! @brief Configure Camera Pins and Initiate Camera.
        Set Quality of Camera to 12 (1-60).
        TODO: Catch exception and retry.
    """
    try:
        camera.init(0, d0=4, d1=5, d2=18, d3=19, d4=36, d5=39, d6=34, d7=35, format=camera.JPEG,
                    framesize=camera.FRAME_VGA, xclk=21, pclk=22, vsync=25, href=23, siod=26, sioc=27, pwdn=-1, reset=-1)
    except:
        camera.deinit()
        camera.init(0, d0=4, d1=5, d2=18, d3=19, d4=36, d5=39, d6=34, d7=35, format=camera.JPEG,
                    framesize=camera.FRAME_VGA, xclk=21, pclk=22, vsync=25, href=23, siod=26, sioc=27, pwdn=-1, reset=-1)
    camera.quality(12)


def ConstructWebPage():
    html = """<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MiniMiST</title>
    <script src="https://code.highcharts.com/highcharts.js"></script>
    <script>
        var isPause;
        var chartVT, chartIT, chart_temp, chart_hum;
        var intervalID_solar, intervalID_sensor, intervalID_stream;
        var count = 0;
        var time_interval = 1000;
        var stream_button_state = 0;

        window.onload = function () {
            isPause = false;
            chartVT = new Highcharts.Chart({
                chart: {
                    renderTo: 'graphVT',
                    zoomType: 'xy',
                    panning: {
                        enabled: true,
                        type: 'xy'
                    },
                    panKey: 'ctrl',
                    type: 'spline'
                },
                title: { text: 'Solar Voltage Graph' },
                series: [{
                    name: "Voltage",
                    showInLegend: false,
                    data: [],
                    zones: [
                        {
                            value: 0.1,
                            color: '#434348'
                        },
                        {
                            value: 0.5,
                            color: '#F45B5B'
                        },
                        {
                            value: 2.5,
                            color: '#f7a35c'
                        },
                        { color: '#90ed7d' }
                    ]
                }],
                xAxis: {
                    type: 'datetime',
                    dateTimeLabelFormats: { second: '%H:%M:%S' }
                },
                yAxis: {
                    title: { text: 'Volatage (V)' }
                },
                plotOptions: {
                    line: {
                        animation: {
                            duration: 1000,
                            defer: 2
                        },
                        dataLabels: { enabled: true }
                    },
                    series: { color: '#308712' }
                },

                credits: { enabled: false }
            });

            chartIT = new Highcharts.Chart({
                chart: {
                    renderTo: 'graphIT',
                    zoomType: 'xy',
                    panning: {
                        enabled: true,
                        type: 'xy'
                    },
                    panKey: 'ctrl',
                    type: 'spline'
                },
                title: { text: 'Solar Current Graph' },
                series: [{
                    name: "Current Time",
                    showInLegend: false,
                    data: [],
                }],
                xAxis: {
                    type: 'datetime',
                    dateTimeLabelFormats: { second: '%H:%M:%S' }
                },
                yAxis: {
                    title: { text: 'Current (I/mA)' },
                },
                plotOptions: {
                    line: {
                        animation: {
                            duration: 1000,
                            defer: 2
                        },
                        dataLabels: { enabled: true }
                    },
                    series: { color: '#660000' }
                },
                credits: { enabled: false }
            });
            chartVI = new Highcharts.Chart({
                chart: {
                    renderTo: 'graphVI',
                    zoomType: 'xy',
                    panning: {
                        enabled: true,
                        type: 'xy'
                    },
                    panKey: 'ctrl',
                    type: 'scatter'
                },
                title: { text: 'VOltage Current' },
                series: [{
                    name: "Volt",
                    showInLegend: false,
                    data: [],
                }],
                xAxis: {
                    title: { text: "Voltage" }
                },
                yAxis: {
                    title: { text: 'Current (I/mA)' },
                },
                plotOptions: {
                    line: {
                        animation: {
                            duration: 1000,
                            defer: 2
                        },
                        dataLabels: { enabled: true }
                    },
                    series: { color: '#660000' }
                },
                credits: { enabled: false }
            });


            chart_temp = new Highcharts.Chart({
                chart: {
                    renderTo: 'temp',
                    zoomType: 'xy',
                    panning: {
                        enabled: true,
                        type: 'xy'
                    },
                    panKey: 'ctrl',
                    type: 'spline'
                },
                title: { text: 'Temperature' },
                series: [{
                    name: "TemperatureC",
                    showInLegend: false,
                    data: []
                }],
                xAxis: {
                    type: 'datetime',
                    dateTimeLabelFormats: { second: '%H:%M:%S' }
                },
                yAxis: {
                    title: { text: 'Temperature (C)' }
                },
                plotOptions: {
                    line: {
                        animation: {
                            duration: 1000,
                            defer: 2
                        },
                        dataLabels: { enabled: true }
                    }
                },
                credits: { enabled: false }
            });

            chart_hum = new Highcharts.Chart({
                chart: {
                    renderTo: 'hum',
                    zoomType: 'xy',
                    panning: {
                        enabled: true,
                        type: 'xy'
                    },
                    panKey: 'ctrl',
                    type: 'spline'
                },
                title: { text: 'Humidity' },
                series: [{
                    name: "Hum",
                    showInLegend: false,
                    data: []
                }],
                xAxis: {
                    type: 'datetime',
                    dateTimeLabelFormats: { second: '%H:%M:%S' }
                },
                yAxis: {
                    title: { text: 'humidity' }
                },
                plotOptions: {
                    line: {
                        animation: {
                            duration: 1000,
                            defer: 2
                        },
                        dataLabels: { enabled: true }
                    }
                },
                credits: { enabled: false }
            });

            // intervalID_solar = setInterval(updatesolar, time_interval);
            // intervalID_sensor = setInterval(updatesensor, 1020);
            setInterval(updatedatetime, 1000);
        }
        function updatedatetime() {
            if (!isPause) {
                var dt = new Date();
                document.getElementById("time").innerHTML = dt.toLocaleTimeString();
                document.getElementById("date").innerHTML = dt.toLocaleDateString();
            }
        }

        function check_interval(chart1, now) {
            return false;
        }

        function updatesolar(callback1) {
            var xhttp = new XMLHttpRequest();
            xhttp.onload = function () {
                if (this.status == 200) {
                    var x = (new Date()).getTime();
                    var temp = JSON.parse(this.responseText);
                    console.log(temp);
                    var y = parseFloat(parseFloat(temp["solar_voltage"]).toFixed(2));
                    var z = parseFloat(parseFloat(temp["solar_current"]).toFixed(3));
                    // var y = parseFloat((Math.random() * 10).toFixed(2));
                    // var z = y * 34 + 29;
                    // if (check_interval(chartVT,x)){chartVT.series.remove(true)};
                    if (chartVT.series[0].data.length > 15) { //TODO check timeinterval between new and first element of series: if large clear data else 
                        chartVI.series[0].addPoint([y, z], true, true, true);
                        chartVT.series[0].addPoint([x, y], true, true, true);
                        chartIT.series[0].addPoint([x, z], true, true, true);
                    } else {
                        chartVI.series[0].addPoint([y, z], true, false, true);
                        chartVT.series[0].addPoint([x, y], true, false, true);
                        chartIT.series[0].addPoint([x, z], true, false, true);
                    }
                    if (count % 5 == 0) {
                        document.getElementById("BatteryLevel").innerHTML = (parseFloat(temp["battery_voltage"]).toFixed(0)) + " %";
                    }
                    count++;
                    document.getElementById("Volt").innerHTML = (parseFloat(temp["solar_voltage"]).toFixed(1)) + " V";
                    document.getElementById("Cur").innerHTML = (parseFloat(temp["solar_current"]).toFixed(2)) + " mA";
                    document.getElementById("Power").innerHTML = (parseFloat(temp["solar_power"]).toFixed(2)) + " mW";
                }
            }
            xhttp.open("GET", "/getsolar", true);
            xhttp.send();
            console.log("solar done");
            setTimeout(() => {
                if (typeof (callback1) === 'function') { callback1(); }
            }, 500);
        }

        function updatesensor() {
            xhrtbl = new XMLHttpRequest();
            xhrtbl.open("GET", "/getsensor", true);
            xhrtbl.send();
            xhrtbl.onload = function () {
                if (this.status == 200) {
                    var response = JSON.parse(this.responseText);
                    var x = (new Date()).getTime();
                    var y = parseFloat(parseFloat(response["temperatureC"]).toFixed(2));
                    var z = parseFloat(parseFloat(response["humidity"]).toFixed(2));
                    console.log(response);
                    if (chart_hum.series[0].data.length > 15) {
                        chart_hum.series[0].addPoint([x, y], true, true, true);
                        chart_temp.series[0].addPoint([x, z], true, true, true);
                    } else {
                        chart_hum.series[0].addPoint([x, y], true, false, true);
                        chart_temp.series[0].addPoint([x, z], true, false, true);
                    }
                    document.getElementById("temperature").innerHTML = response["temperatureC"] + "°C";
                    document.getElementById("temperaturef").innerHTML = response["temperatureF"] + "°F";
                    document.getElementById("humidity").innerHTML = response["humidity"] + "%";
                }
            }
            xhrtbl.onerror = function () {
                console.log("Error Occured");
            }
            console.log("Sensor done");
        }

        function encode64(inputStr) {
            var b64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=";
            var outputStr = "data:image.gif;base64,";
            var i = 0;

            while (i < inputStr.length) {
                var byte1 = inputStr.charCodeAt(i++) & 0xff;
                var byte2 = inputStr.charCodeAt(i++) & 0xff;
                var byte3 = inputStr.charCodeAt(i++) & 0xff;

                var enc1 = byte1 >> 2;
                var enc2 = ((byte1 & 3) << 4) | (byte2 >> 4);

                var enc3, enc4;
                if (isNaN(byte2)) {
                    enc3 = enc4 = 64;
                } else {
                    enc3 = ((byte2 & 15) << 2) | (byte3 >> 6);
                    if (isNaN(byte3)) {
                        enc4 = 64;
                    } else {
                        enc4 = byte3 & 63;
                    }
                }
                outputStr += b64.charAt(enc1) + b64.charAt(enc2) + b64.charAt(enc3) + b64.charAt(enc4);
            }
            return outputStr;
        }

        function loadImage(callback1, callback2) {

            var xhr1 = new XMLHttpRequest();
            xhr1.open("GET", "/getimage", true);
            xhr1.overrideMimeType('text/plain; charset=x-user-defined');
            xhr1.send();
            xhr1.onload = function () {
                if (this.status == 200) {
                    var image = document.getElementById("sat-image");
                    var response = xhr1.responseText;
                    source = encode64(response);
                    image.src = source;
                }
            }
            xhr1.onerror = function () {
                console.log("Error Occured");
            }
            console.log("Image done");

            // setTimeout(() => {
            //     if (typeof (callback1) === 'function' || typeof (callback2) === 'function') { callback1(callback2); }
            // }, 500);
        }

        function stream(stream_button) {
            stream_button_state = 1 - stream_button_state;
            var counterint = 0;
            var counterimg = 0;
            var countersen = 0;
            var countersol = 0;
            enable_stream_button(stream_button, stream_button_state);
            if (stream_button_state) {
                intervalID_stream = setInterval(() => {
                    console.log("Interval start", counterint++);
                    setTimeout(() => {
                        let start = (new Date()).getMilliseconds();
                        loadImage();
                        let end = (new Date()).getMilliseconds();
                        console.log("Load image end", counterimg++, "Time : ", end, "-", start, " = ", end - start);
                        setTimeout(() => {
                            updatesensor();
                            console.log("sensor end", countersen++);
                            setTimeout(() => {
                                updatesolar();
                                console.log("Solar end", countersol++);
                            }, 500);
                        }, 500);
                    }, 0);
                }, 5000);
            }
            else {
                clearInterval(intervalID_stream);
            }
        }
        function enable_stream_button(stream_button, state) {
            if (state) {
                stream_button.innerHTML = "Stream: ON";
                stream_button.style.background = "green";
                stream_button.style.color = "lightgreen";
                ["imagebutton", "solarbutton", "sensorbutton"].forEach((button) => {
                    document.getElementById(button).disabled = true;
                })
            }
            else {
                stream_button.innerHTML = "Stream: OFF";
                stream_button.style.background = "lightgrey";
                stream_button.style.color = "grey";
                ["imagebutton", "solarbutton", "sensorbutton"].forEach((button) => {
                    document.getElementById(button).disabled = false;
                })
            }
        }

    </script>
    <link rel="stylesheet" href="https://unpkg.com/98.css">
    <style>
        /* This covers the entire screen where the container is to be placed upon */
        body {
            margin: 0;
            padding: 0;
        }

        /* Implement grid in css. Splits the container into grid that can be used to allocate different sections*/
        .Container {
            width: 100vw;
            /* The viewport width (vw) is relative to the width of the browser*/
            height: 100vh;

            display: grid;

            grid-template-columns: 2fr 0.6fr 1fr;
            /* 4 columes (image image button table)*/
            grid-template-rows: 50px 1.5fr 0.8fr 0.2fr 55px;
            /* 5 Rows (Header graph table datetime footer)*/
            grid-template-areas:
                "Header Header Header"
                "Image Graph Graph"
                "Image ControlImg Sensor"
                "Image ControlImg Datetime"
                "Footer Footer Footer"
            ;

            padding: 10px;
            gap: 10px;
            box-sizing: border-box;
            background-image: -webkit-linear-gradient(45deg, #ffffff 10%, #3c3a3a81 120%);

            box-shadow: inset 0 0 10px #000000;

            /* The border is size of the window*/
        }

        .Container .Header,
        .Footer,
        .Graph,
        .ControlImg,
        .Image,
        .Datetime,
        .Sensor {
            padding: 9px;
            
            border: 1px solid #000000;
            -moz-box-shadow: inset 0 0 10px #000000;
            -webkit-box-shadow: inset 0 0 10px #000000;
            box-shadow: 0 0 10px #000000;
            border-radius: 0px 0px 0px 0px;
            box-sizing: border-box;
        }

        .Header {
            grid-column: 1/4;
            grid-row: 1;

            font-family: 'Times New Roman', Times, serif;
            font-size: x-large;
            color: #070741;
            text-align: center;
            justify-content: center;
            align-content: center;
        }

        .Footer {
            grid-row: 5;
            grid-column: 1/4;
            line-height: 75%;

            padding-top: 12px;
            overflow-y: hidden;

        }

        .Footer::-webkit-scrollbar {
            display: none;
            /* for Chrome, Safari, and Opera */
        }

        /* @keyframes loadimage {} */

        .Image {
            grid-row: 2/5;
            grid-column: 1;
            overflow: auto;
            display: flex;
            object-position: center;
            justify-content: center;


        }

        .Image img {
            transform: rotate(0.25turn);
            max-width: 100%;
        }

        .ControlImg {
            grid-row: 3 / 5;
            grid-column: 2;
            padding: 10px;
        }

        .ControlImg #BatteryLevel {
            text-align: center;
        }

        .Graph {
            grid-row: 2;
            grid-column: 2/4;
            overflow-y: scroll;
            scroll-snap-type: y mandatory;
            scroll-padding: 10px;
            scroll-behavior: auto;
            gap: 5px;

        }

        .Graph .graphs {
            scroll-snap-align: start;
            scroll-snap-stop: normal;
        }

        .Sensor {
            grid-row: 3;
            grid-column: 3;
            align-items: center;
            overflow: auto;
            padding: 1px;

        }

        .Datetime {
            grid-row: 4;
            grid-column: 3;
            padding: 7px;
            border: 2px solid #000000;

        }

        .sensor-data {
            overflow: auto;
            position: fixed;
            top: 0%;
            height: 60%;
        }

        .side {
            display: inline-block;
            vertical-align: middle;
            position: relative;
            float: right;
            margin-right: 17px;
        }

        h4 {
            margin-bottom: 30%;
            margin-top: 2%;

        }

        button {
            width: 100%;
            table-layout: fixed;
            border-collapse: collapse;
        }

        li.fixed {
            position: -webkit-sticky;
            /* position: sticky; */
            top: 0;
            list-style-type: none;
        }

        li {
            margin-left: 20px;
            line-height: 15px;
        }

        @media screen and (max-width: 653px) {
            body {
                width: auto !important;
                overflow-x: hidden !important;
                overflow-y: scroll;
                /* has to be scroll, not auto */
                -webkit-overflow-scrolling: touch;
            }

            .Container {
                grid-template-columns: 100%;
                width: auto;
                height: max-content;
                /* 1 colume (image)*/
                grid-template-rows: 50px 200px 300px 240px 160px 45px 65px;
                /* 5 Rows (Header graph table datetime footer)*/
                grid-template-areas:
                    "Header"
                    "ControlImg"
                    "Image"
                    "Graph"
                    "Sensor"
                    "Datetime"
                    "Footer"
                ;
                background-image: -webkit-linear-gradient(45deg, #ffffff 10%, #3c3a3a81 150%);

            }

            *,
            *:before,
            *:after {
                box-sizing: inherit;
            }

            .Header {
                grid-column: 1;
                grid-row: 1;

            }

            @media (max-width: 330px) {
                .Header {
                    font-size: large;
                }
            }

            .ControlImg {
                grid-column: 1;
                grid-row: 2;
            }

            .Image {
                grid-column: 1;
                grid-row: 3;
            }

            .Graph {
                grid-column: 1;
                grid-row: 4;
            }

            .Sensor {
                grid-column: 1;
                grid-row: 5;
            }

            .Datetime {
                grid-column: 1;
                grid-row: 6;
            }

            .Footer {
                grid-column: 1;
                grid-row: 7;
                padding-top: 18px;
                overflow-y: auto;
            box-shadow: 0 0 10px #646161;


            }
        }
    </style>
</head>

<body>
    <div class="Container">
        <div class="Header ">
            <b>ESP32 Satellite - MiniMiST</b>
        </div>
        <div class="Image">
            <img id="sat-image" />
        </div>
        <div class="ControlImg ">
            <button class="btn" id="streambutton" onclick="stream(this)">Stream</button><br><br>
            <button class="btn" id="imagebutton" onclick="loadImage()">Load Image</button>
            <button class="btn" id="sensorbutton" onclick="updatesensor()">Sensor Data</button>
            <button class="btn" id="solarbutton" onclick="updatesolar()">Solar Data</button>
            <!-- <br><br> -->
            <!-- To add space we use &nbsp -->
            <!-- <button type="button" onclick="download()">Download Image</button> -->
            <hr>
            <p>
                <center>Battery Remaining</center>
            <h4>
                <div id="BatteryLevel">N/A</div>
            </h4>
            </p>
        </div>
        <div class="Graph tree-view">
            <div class="graphs" id="graphVT" style=" height: 220px;width: auto;"></div><br>
            <div class="graphs" id="graphIT" style=" height: 220px;width: auto;"></div><br>
            <div class="graphs" id="graphVI" style=" height: 220px;width: auto;"></div><br>
            <div class="graphs" id="temp" style=" height: 220px;width: auto;"></div><br>
            <div class="graphs" id="hum" style=" height: 220px;width: auto;"></div>
        </div>
        <div class="Sensor">
            <ul id="sensor-data" class="tree-view">
                <li class="fixed">
                    <center><u><b>DHT11 Readings</u></b></center>
                </li>
                <li> Temperature: <strong>
                        <div class="side " id="temperature">--</div>
                    </strong></li>
                <li> Temperature: <strong>
                        <div class="side " id="temperaturef">--</div>
                    </strong> </li>
                <li>Humidity: <strong>
                        <div class="side" id="humidity">--</div>
                    </strong> </li>
                <li class="fixed">
                    <center><u><b>Solar Readings</b></u></center>
                </li>
                <li> Voltage: <strong>
                        <div class="side " id="Volt">--</div>
                    </strong></li>
                <li> Current: <strong>
                        <div class="side " id="Cur">--</div>
                    </strong> </li>
                <li>Power: <strong>
                        <div class="side" id="Power">--</div>
                    </strong> </li>
            </ul>
        </div>

        <div id="Datetime">
            <ul class="tree-view">
                <li><b>Date/Time:</b></li>
                <li><span id="date">DD/MM/YYYY </span> <span id="time">HH:MM:SS AM/PM</span></li>
            </ul>
        </div>

        <div class="Footer">
            <center><b>Project by: Kocin Sabareeswaran Bama</b></center>
            <center>
                <p> Tools used: HTML, CSS, JavaScript, Ajax, Micropython, C, Kicad </p>
            </center>
        </div>

    </div>
</body>

</html>"""
    return html


def get_sensor_readings():
    """!  @brief Reads Humidity, Temperature and Hall readings from DHT11 sensor and inbuilt Hallsensor.
        The DHT11 sensor is placed in Pin 13.
        Pin 36 & 39 are connected to the hall effect sensor

        @return JSON:
            -humidity Humidity
            -tempratureC Temperature in Celsius
            -tempratureF Temperature in Fahrenheit
        TODO: Catch Exception and send Null Data.
        TODO: Add Heat Index to the return JSON.
    """
    sensor_readings = {"temperatureC": "-1", "humidity": "-1", "temperatureF": "-1","Error":False}
    try:
        sensordht.measure()
        temperatureC = sensordht.temperature()
        sensor_readings["temperatureC"] = str(temperatureC)
        sensor_readings["humidity"] = str(sensordht.humidity())
        sensor_readings["temperatureF"] = str(temperatureC * (9/5) + 32.0)
        # sensor_readings["hall"] = str(esp32.hall_sensor()) # Stoped becausee the pins interfere with Camera Pins
        time.sleep(0.1)
    except OSError as e:
        print(e)
        print('Failed to read sensor.')
        sensor_readings["Error":True]
    return sensor_readings


def get_solar_readings():
    """! @brief Get Voltage reading from solar panels and battery.
        Convert the analog reading to voltage.

        @return JSONString:
            -voltage_solar Voltage received from Solar Panels
            -current_solar Current received from Solar Panels
            -power_solar   Power received from Solar Panels
            -voltage_batt  Voltage remaining in Battery
    """
    solar_readings = {}
    read_volt_solar = solarvolt.read()
    time.sleep(0.1)
    read_volt_batt = battvolt.read()
    print(read_volt_batt)
    # @attention There is an addition of 0.13V (163 analog value) to the voltage that is read.
    # This is due to the inaccuracy in the measurements and to calibrate the reading.
    # The value is declared after measureing different value and comapring with real value.
    # It might vary depending on your ESP32 module or device.
    vout = (read_volt_solar * (3.3/4095) + 0.13) if (read_volt_solar > 12) else (read_volt_solar * (3.3/4095))
    batt = (read_volt_batt * (3.3/4095) + 0.13) if (read_volt_batt > 12) else (read_volt_batt * (3.3/4095))

    volt_in = (vout * ((21600+8170)/8170))
    current = (volt_in*1000) / (21600+8100)
    power = current * volt_in
    battery_volt =  100 * ((batt * 2 - 2.7))/(4.7-2.7)
    
#    print((batt))
#    print(battery_volt)
    
    solar_readings["solar_voltage"] = str(volt_in)
    solar_readings["solar_current"] = str(current)
    solar_readings["solar_power"] = str(power)
    solar_readings["solar_voltage_out"] = str(vout)
    if battery_volt < 0:
        solar_readings["battery_voltage"] = "0"
    elif battery_volt > 100:
        solar_readings["battery_voltage"] = "100"
    else:
        solar_readings["battery_voltage"] = str(battery_volt)
    time.sleep(0.1)
    return solar_readings


def get_image():
    """ @brief The function camptures an image from the initated camera.
    Prints the Time taken for campture.
    @exception The Pin configures for camera might be used for other values and not assigned back to Camera

    @return buffer object that has the image.
    """
    cam_start_time = time.ticks_ms()
    print("Taking a photo...")
    buf = camera.capture()
    if (not buf):
        print("Camera Capture failed")
        camera_false_count += 1
        if (camera_false_count >5):
            machine.reset()
        return ""
    cam_end_time = time.ticks_ms()
    print("Time to capture photo:"+str(cam_end_time-cam_start_time))
    camera_false_count = 0
    return buf


def blink(led, val):
    """! @brief used to set the value of led to ON or OFF.
    @param led
        -led1 Pin 12
        -led2 Pin 2 onBoard LED
        -led3 Pin 15
    @param val
        -1 ON
        -0 OFF
    """
    led.value(val)
    time.sleep(0.15)


connect_wifi()

# Create Internet socket interface for TCP web-server
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
print("Before s.bind: ", socket.getaddrinfo(ipaddr, 80)[0][-1])
address = ipaddr

# Assign and bind port 80 for HTTP web-server socket !!!Change the IP address to bind to the IP addr of ESP32
s.bind((address, 80))
s.listen(7)  # Configure for listening maximum 5 web-clients
print("Server Started and Running at :" + address)
blink(led2, 1)
i = 0

while True:
    try:
        response = ""
        if gc.mem_free() < 102000:
            gc.collect()
        # accept new connection!!!Conn is a new socket object to communicate data on new conn. addr is the clients addr
        conn, addr = s.accept()
        blink(led2, 1)
        conn.settimeout(1.0)
        print('~~~~~> Got a connection from %s' %
              str(addr))  # Print the client address
        request = str(conn.recv(1024))  # Collect client request
        conn.settimeout(None)
        blink(led2, 0)
        # Print the web-client request
        print('~~~~~> Content = %s' % request[2:15])
        ifimage = request.find('/getimage')
        ifsensor = request.find('/getsensor')
        ifsolar = request.find('/getsolar')
        if ifimage == 6:
            buzzer.notify1()
            blink(led1,1)
            start =  time.ticks_ms()
            init_cam()
            response = get_image()
            camera.deinit()
            content_type = 'image/jpeg'
            end =  time.ticks_ms()
            blink(led1,0)
            buzzer.notify2()
        elif ifsensor == 6:
            start =  time.ticks_ms()
            sensordht.measure()
            response = json.dumps(get_sensor_readings())
            content_type = 'applications/json'
            end =  time.ticks_ms()
        elif ifsolar == 6:
            start =  time.ticks_ms()
            response = json.dumps(get_solar_readings())
            content_type = 'applications/json'
            end =  time.ticks_ms()
        else:
            start =  time.ticks_ms()
            response = ConstructWebPage()  # Construct the web page
            content_type = 'text/html'
            end =  time.ticks_ms()
        
        print("=>Time to create response: ", end-start)    
        conn.send('HTTP/1.1 200 OK\n')
        conn.send('Content-Type: ' + content_type + '\n')
        conn.send('Connection: close\n\n')
        conn.sendall(response)    
        conn.close()
        print("==> Response sent")
    except OSError as e:
        buzzer.notify3()
        conn.close()
        print('Connection closed ' + str(e))
    except Exception as e:
        buzzer.notify3()
        print(e)
        conn.close()

camera.deinit()
