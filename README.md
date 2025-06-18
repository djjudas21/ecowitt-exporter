# ecowitt-exporter

Ecowitt exporter for Prometheus

The WiFi-enabled Ecowitt weather stations can export metrics in a number of protocols to various online weather services, as a push operation.
They also support pushing to a custom endpoint in a choice of two protocols, Ecowitt or Wunderground. Blogger Ernest Neijenhuis has
[checked out the protocols](https://www.pa3hcm.nl/?p=2095) and found that the Ecowitt protocol is more comprehensive. He then wrote a Python
app called [Ecowither](https://github.com/pa3hcm/ecowither) to gateway the Ecowitt metrics into InfluxDB.

Here I am building on his work to present the Ecowitt metrics as an exporter for Prometheus.

This exporter runs on a single HTTP port (default `8088`) and provides two endpoints:

* `/report` where the Ecowitt weather station should POST its data
* `/metrics` where Prometheus can scrape metrics with a GET request

This diagram shows the rough flow of information:

![Diagram](/images/ecowitt.drawio.png)

1. Ecowitt sensors submit their readings to the Ecowitt gateway via RF
1. Ecowitt gateway aggregates the data and submits it to the Ecowitt Exporter, running as a container
1. Prometheus periodically scrapes data from the Exporter
1. Grafana queries metrics from Prometheus to draw graphs

This exporter supports setting optional physical locations for some of the remote sensors. Setting
the locations here causes the Prometheus metrics to be labelled, which may be helpful when writing
queries or dashboards later.

## Breaking changes

> [!WARNING]  
> Version v1.x breaks compatibility with previous versions of the ecowitt exporter.
> Metrics have changed names, labels are now used, and any Prometheus queries you have written will need modification.
> Support for InfluxDB has been dropped.

## Supported hardware

Most Ecowitt weather stations and sensors should work fine with this exporter.
The following hardware has been explicitly tested. If you have info about any hardware
that does or doesn't work, please raise an issue so I can update the list.

### Weather stations

- WS2910 Weather Station
- GW1100 Wi-Fi Gateway

### Sensors

- WS69 Wireless 7-in-1 Outdoor Sensor Array
- WS90 7-in-1 Outdoor Anti-vibration Haptic Sensor Array
- WH41/WH43 PM2.5 Air Quality Sensor
- WH57 Outdoor Lightning Sensor
- WN31/WH31 Multi-Channel Temperature & Humidity Sensor
- WN32/WH32 Single-Channel Temperature & Humidity Sensor
- WN36 Floating Pool Temperature Sensor
- WH51 Soil Moisture Meter

## Note about Ecowitt firmware

It seems that an Ecowitt WS2910 with firmware v5.1.1 has a bug when writing out HTTP headers, which causes it to not work with Flask.
This [has been reported](https://github.com/pallets/werkzeug/issues/2734) to Flask, but closed as WONTFIX because the underlying problem
is with the Ecowitt firmware.

It is possible to work around this issue by fronting this exporter with an NGINX reverse proxy (such as a Kubernetes Ingress),
because NGINX magically fixes the headers on the fly.

## Environment variables

Set the units for the export of each metric. Ecowitt weather stations always take measurements in Imperial.
This exporter converts them on the fly if necessary, to present them to Prometheus in your desired format.
Metric/SI is always the default. People in the USA will probably want to set everything to Imperial
alternatives, while Brits will likely want a mixture of both!

All units are expressed in lower case and without slashes, for simplicity. Apologies to scientists,
for whom this will be a difficult time.

| Variable           | Default | Choices                            | Meaning                                                                  |
|--------------------|---------|------------------------------------|--------------------------------------------------------------------------|
| `DEBUG`            | `no`    | `no`, `yes`                        | Enable extra output for debugging                                        |
| `TEMPERATURE_UNIT` | `c`     | `c`, `f`, `k`                      | Temperature in Celsius, Fahrenheit or Kelvin                             |
| `PRESSURE_UNIT`    | `hpa`   | `hpa`, `in`, `mmhg`                | Pressure in hectopascals (millibars), inches of mercury or mm of mercury |
| `WIND_UNIT`        | `kmh`   | `kmh`, `mph`, `ms`, `knots`, `fps` | Speed in km/hour, miles/hour, metres/second, knots or feet/second        |
| `RAIN_UNIT`        | `mm`    | `mm`, `in`                         | Rainfall in millimetres or inches                                        |
| `IRRADIANCE_UNIT`  | `wm2`   | `wm2`, `lx`, `fc`                  | Solar irradiance in Watts/m^2                                            |
| `DISTANCE_UNIT`    | `km`    | `km`, `mi`                         | Distance from the last lightning in kilometers                           |
| `AQI_STANDARD`     | `uk`    | `uk`, `epa`, `mep`, `nepm`         | Air Quality Index standard in UK DAQI, US EPA, China MEP, Australia NEPM |
| `OUTDOOR_LOCATION` |         |                                    | Physical location of outdoor Ecowitt sensor array                        |
| `INDOOR_LOCATION`  |         |                                    | Physical location of indoor Ecowitt gateway                              |
| `TEMP1_LOCATION`   |         |                                    | Physical location of Ecowitt channel 1 temperature sensor                |
| `TEMP2_LOCATION`   |         |                                    | Physical location of Ecowitt channel 2 temperature sensor                |
| `TEMP3_LOCATION`   |         |                                    | Physical location of Ecowitt channel 3 temperature sensor                |
| `TEMP4_LOCATION`   |         |                                    | Physical location of Ecowitt channel 4 temperature sensor                |
| `TEMP5_LOCATION`   |         |                                    | Physical location of Ecowitt channel 5 temperature sensor                |
| `TEMP6_LOCATION`   |         |                                    | Physical location of Ecowitt channel 6 temperature sensor                |
| `TEMP7_LOCATION`   |         |                                    | Physical location of Ecowitt channel 7 temperature sensor                |
| `TEMP8_LOCATION`   |         |                                    | Physical location of Ecowitt channel 8 temperature sensor                |

If you want to use one of the units that is not yet supported, please [open an issue](https://github.com/djjudas21/ecowitt-exporter/issues)
and request it. I can add the code to convert and display other units if there is demand.

## Deployment

This project is available as a Docker image [djjudas21/ecowitt-exporter](https://hub.docker.com/r/djjudas21/ecowitt-exporter) which can be run as a
standalone container, but the recommended way to run it is in Kubernetes via the [Helm chart](https://github.com/djjudas21/charts/tree/main/charts/ecowitt-exporter) which is also available on [ArtifactHub](https://artifacthub.io/packages/helm/djjudas21/ecowitt-exporter).
The Helm chart also supports integration with the [Prometheus Operator](https://github.com/prometheus-operator/prometheus-operator) and will
create ServiceMonitor resources to enable automatic scraping.

```console
helm repo add djjudas21 https://djjudas21.github.io/charts/
helm repo update djjudas21
helm install -n monitoring ecowitt-exporter djjudas21/ecowitt-exporter
```
## Grafana

An accompanying [Grafana dashboard](/grafana/EcowittWeatherStation.json)
is available in this repo and can be imported manually into your Grafana instance.

This screenshot was taken on a standard 1080p laptop. The dashboard looks a lot better on a 2.5K or 4K display.

![Grafana](/grafana/EcowittWeatherStation.png)

Currently all the units are hard-coded in this dashboard and I haven't found a way to make them change automatically depending on your exporter unit settings. Instead, you will have to manually change each visualisation in this dashboard to be the correct unit that you have configured in the exporter.

## How to configure your weather station

After deploying via Helm, it will print some output to explain how to find the IP and/or hostname of the exporter running in Kubernetes.

Use the WSView Plus all to configure the integration. Go into the device, scroll across until Customized and set the following:

* Customized: Enable
* Protocol: Ecowitt
* Server IP / Hostname: the IP or hostname that Helm gave you
* Path: `/report`
* Port: `8088` unless you are using an Ingress, in which case probably `80`
* Upload interval: `60`

Then hit Save. It seems to take a couple of minutes for the weather station to submit its first reading.

## Polling frequency

The various Ecowitt sensors have hard-coded intervals that they submit their readings to the weather
station or gateway over RF. These are deliberately staggered to minimise the chance of interference.

| Device | Reporting interval |
|--------|------------------------------|
| WS69 Sensor Array | 16 seconds |
| WS90 Haptic Sensor Array | 8.8 seconds |
| WH41/WH43 PM2.5 Air Quality Sensor | 10 minutes |
| WH57 Lightning Sensor | 79 seconds |
| WN31/WH31 Temperature & Humidity Sensor | 61 seconds |
| WN32/WH32 Temperature & Humidity Sensor | 64 seconds |
| WN36 Floating Pool Temperature Sensor | 60 seconds |
| WH51 Soil Moisture Meter | 70 seconds |

The weather station or gateway then has a configurable upload interval (which defaults to 60 seconds)
that they report the aggregated data to the Ecowitt Exporter.

The scrape interval that Prometheus scrapes data from the Exporter should be the same as the interval
that the gateway uploads it to the Exporter. It is currently hard-coded to 60 seconds. In a future
release it may be configurable.

There is a tradeoff here: scraping more frequently means more disk space required for Prometheus to
store the metrics. However, we can see from the table above that if the WS69 instrument reports every
16 seconds but the gateway only uploads every 60 seconds, we only get to see about 1 in 4 of the
actual measurements taken. The rest are lost. This may or may not be OK, depending on how fast weather
conditions are changing.

## Testing

The exporter script can be run locally simply with:

```
python ecowitt_exporter.py
```

You can set environment variables, e.g. the physical location fields for testing:

```
TEMP1_LOCATION=Garden python ecowitt_exporter.py
```

Real data has been captured from a Ecowitt GW1100A with this exporter in debug mode. It has been
provided in `data.txt` for testing purposes.

A POST request from an Ecowitt device can be simulated with curl:

```
curl -d @data.txt -X POST http://127.0.0.1:8088/report
```

We can then view the corresponding Prometheus metrics with a simple GET request (output has been truncated because it is very long):

```
curl http://127.0.0.1:8088/metrics
# HELP ecowitt_stationtype_info Ecowitt station type
# TYPE ecowitt_stationtype_info gauge
ecowitt_stationtype_info{stationtype="GW1100A_V2.4.1"} 1.0
# HELP ecowitt_freq_info Ecowitt radio frequency
# TYPE ecowitt_freq_info gauge
ecowitt_freq_info{freq="868M"} 1.0
# HELP ecowitt_model_info Ecowitt model
# TYPE ecowitt_model_info gauge
ecowitt_model_info{model="GW1100A"} 1.0
# HELP ecowitt_temp Temperature
# TYPE ecowitt_temp gauge
ecowitt_temp{location="indoor",sensor="indoor",unit="c"} 30.1
ecowitt_temp{location="outdoor",sensor="outdoor",unit="c"} 17.7
ecowitt_temp{location="Garden",sensor="ch1",unit="c"} 23.5
ecowitt_temp{location="None",sensor="ch2",unit="c"} 21.7
ecowitt_temp{location="None",sensor="ch3",unit="c"} 24.4
ecowitt_temp{location="None",sensor="ch4",unit="c"} 22.8
ecowitt_temp{location="None",sensor="ch5",unit="c"} 24.3
ecowitt_temp{location="None",sensor="ch6",unit="c"} 25.4
ecowitt_temp{location="None",sensor="ch8",unit="c"} 23.3
# HELP ecowitt_humidity Relative humidity
# TYPE ecowitt_humidity gauge
ecowitt_humidity{location="indoor",sensor="indoor",unit="percent"} 41.0
ecowitt_humidity{location="outdoor",sensor="outdoor",unit="percent"} 75.0
ecowitt_humidity{location="Garden",sensor="ch1",unit="percent"} 57.0
ecowitt_humidity{location="None",sensor="ch2",unit="percent"} 61.0
ecowitt_humidity{location="None",sensor="ch3",unit="percent"} 54.0
ecowitt_humidity{location="None",sensor="ch4",unit="percent"} 62.0
ecowitt_humidity{location="None",sensor="ch5",unit="percent"} 54.0
ecowitt_humidity{location="None",sensor="ch6",unit="percent"} 45.0
ecowitt_humidity{location="None",sensor="ch8",unit="percent"} 58.0
# HELP ecowitt_winddir Wind direction
# TYPE ecowitt_winddir gauge
ecowitt_winddir 173.0
# HELP ecowitt_uv UV index
# TYPE ecowitt_uv gauge
ecowitt_uv 0.0
# HELP ecowitt_pm25 PM2.5 concentration
# TYPE ecowitt_pm25 gauge
ecowitt_pm25{sensor="ch2",series="realtime",unit="μgm3"} 3.0
ecowitt_pm25{sensor="ch2",series="avg_24h",unit="μgm3"} 2.6
# HELP ecowitt_aqi Air quality index
# TYPE ecowitt_aqi gauge
ecowitt_aqi{standard="uk"} 1.0
# HELP ecowitt_batterystatus Battery status
# TYPE ecowitt_batterystatus gauge
ecowitt_batterystatus{sensor="wh65batt"} 0.0
ecowitt_batterystatus{sensor="batt1"} 0.0
ecowitt_batterystatus{sensor="batt2"} 0.0
ecowitt_batterystatus{sensor="batt3"} 0.0
ecowitt_batterystatus{sensor="batt4"} 0.0
ecowitt_batterystatus{sensor="batt5"} 0.0
ecowitt_batterystatus{sensor="batt6"} 0.0
ecowitt_batterystatus{sensor="batt8"} 0.0
# HELP ecowitt_batterylevel Battery level
# TYPE ecowitt_batterylevel gauge
ecowitt_batterylevel{sensor="pm25batt2"} 5.0
ecowitt_batterylevel{sensor="wh57batt"} 4.0
# HELP ecowitt_batteryvoltage Battery voltage
# TYPE ecowitt_batteryvoltage gauge
ecowitt_batteryvoltage{sensor="soilbatt1",unit="volt"} 1.7
# HELP ecowitt_solarradiation Solar irradiance
# TYPE ecowitt_solarradiation gauge
ecowitt_solarradiation{unit="wm2"} 29.22
# HELP ecowitt_barom Barometer
# TYPE ecowitt_barom gauge
ecowitt_barom{sensor="relative",unit="hpa"} 1024.01
ecowitt_barom{sensor="absolute",unit="hpa"} 1008.6
# HELP ecowitt_vpd Vapour pressure deficit
# TYPE ecowitt_vpd gauge
ecowitt_vpd{unit="hpa"} 5.08
# HELP ecowitt_windspeed Wind speed
# TYPE ecowitt_windspeed gauge
ecowitt_windspeed{sensor="windspeed",unit="kmh"} 0.0
ecowitt_windspeed{sensor="windgust",unit="kmh"} 5.41
ecowitt_windspeed{sensor="maxdailygust",unit="kmh"} 11.15
# HELP ecowitt_windspeed_beaufort Wind Beaufort scale
# TYPE ecowitt_windspeed_beaufort gauge
ecowitt_windspeed_beaufort 0.0
# HELP ecowitt_rain Rainfall
# TYPE ecowitt_rain gauge
ecowitt_rain{sensor="rate",unit="mm"} 0.0
ecowitt_rain{sensor="event",unit="mm"} 0.0
ecowitt_rain{sensor="hourly",unit="mm"} 0.0
ecowitt_rain{sensor="daily",unit="mm"} 0.0
ecowitt_rain{sensor="weekly",unit="mm"} 17.7
ecowitt_rain{sensor="monthly",unit="mm"} 30.7
ecowitt_rain{sensor="yearly",unit="mm"} 210.3
ecowitt_rain{sensor="total",unit="mm"} 210.3
# HELP ecowitt_lightning Lightning distance
# TYPE ecowitt_lightning gauge
ecowitt_lightning{unit="km"} 34.0
# HELP ecowitt_lightning_num Lightning daily count
# TYPE ecowitt_lightning_num gauge
ecowitt_lightning_num 0.0
# HELP ecowitt_lightning_time Lightning last strike
# TYPE ecowitt_lightning_time gauge
ecowitt_lightning_time 1.747849832e+09
# HELP ecowitt_wh90 WS90 electrical energy stored
# TYPE ecowitt_wh90 gauge
# HELP ecowitt_soilmoisture Soil moisture
# TYPE ecowitt_soilmoisture gauge
ecowitt_soilmoisture{sensor="soilmoisture1",unit="percent"} 0.0
```

## Building and running locally
```
podman build -t ecowitt-exporter .
podman run -d --rm -p 8088:8088 -e DEBUG=yes ecowitt-exporter
```
