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

If you want to use one of the units that is not yet supported, please [open an issue](https://github.com/djjudas21/ecowitt-exporter/issues)
and request it. I can add the code to convert and display other units if there is demand.

## Deployment

This project is available as a Docker image [djjudas21/ecowitt-exporter](https://hub.docker.com/r/djjudas21/ecowitt-exporter) which can be run as a
standalone container, but the recommended way to run it is in Kubernetes via the [Helm chart](https://github.com/djjudas21/charts/tree/main/charts/ecowitt-exporter).
The Helm chart also supports integration with the [Prometheus Operator](https://github.com/prometheus-operator/prometheus-operator) and will
create ServiceMonitor resources to enable automatic scraping.

```console
helm repo add djjudas21 https://djjudas21.github.io/charts/
helm repo update djjudas21
helm install -n monitoring ecowitt-exporter djjudas21/ecowitt-exporter
```

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

## Testing

Real data has been captured from a Ecowitt GW1100A with this exporter in debug mode. It has been provided in `data.txt` for testing purposes.

A POST request from an Ecowitt device can be simulated with curl:

```
curl -d @data.txt -X POST http://127.0.0.1:8088/report
```

We can then view the corresponding Prometheus metrics with a simple GET request (output has been truncated because it is very long):

```
curl http://127.0.0.1:8088/metrics                    
# HELP ecowitt_stationtype_info Ecowitt station type
# TYPE ecowitt_stationtype_info gauge
ecowitt_stationtype_info{stationtype="GW1100A_V2.4.0"} 1.0
# HELP ecowitt_freq_info Ecowitt radio frequency
# TYPE ecowitt_freq_info gauge
ecowitt_freq_info{freq="868M"} 1.0
# HELP ecowitt_model_info Ecowitt model
# TYPE ecowitt_model_info gauge
ecowitt_model_info{model="GW1100A"} 1.0
# HELP ecowitt_temp_c Temperature
# TYPE ecowitt_temp_c gauge
ecowitt_temp_c{sensor="indoor"} 29.4
ecowitt_temp_c{sensor="ch1"} 20.0
ecowitt_temp_c{sensor="ch2"} 21.3
ecowitt_temp_c{sensor="ch3"} 22.0
ecowitt_temp_c{sensor="ch4"} 21.4
ecowitt_temp_c{sensor="ch5"} 23.0
ecowitt_temp_c{sensor="ch6"} 24.1
ecowitt_temp_c{sensor="ch8"} 22.9
# HELP ecowitt_humidity_percent Relative humidity
# TYPE ecowitt_humidity_percent gauge
ecowitt_humidity_percent{sensor="indoor"} 31.0
ecowitt_humidity_percent{sensor="ch1"} 40.0
ecowitt_humidity_percent{sensor="ch2"} 48.0
ecowitt_humidity_percent{sensor="ch3"} 38.0
ecowitt_humidity_percent{sensor="ch4"} 56.0
ecowitt_humidity_percent{sensor="ch5"} 40.0
ecowitt_humidity_percent{sensor="ch6"} 38.0
ecowitt_humidity_percent{sensor="ch8"} 42.0
# HELP ecowitt_winddir_degree Wind direction
# TYPE ecowitt_winddir_degree gauge
ecowitt_winddir_degree 0.0
# HELP ecowitt_uv UV index
# TYPE ecowitt_uv gauge
ecowitt_uv 0.0
# HELP ecowitt_pm25 PM2.5 concentration
# TYPE ecowitt_pm25 gauge
ecowitt_pm25{sensor="ch2",series="realtime"} 11.0
ecowitt_pm25{sensor="ch2",series="avg_24h"} 19.5
# HELP ecowitt_aqi Air quality index
# TYPE ecowitt_aqi gauge
ecowitt_aqi 2.0
# HELP ecowitt_batterystatus Battery status
# TYPE ecowitt_batterystatus gauge
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
# HELP ecowitt_solarradiation_wm2 Solar irradiance
# TYPE ecowitt_solarradiation_wm2 gauge
ecowitt_solarradiation_wm2 0.0
# HELP ecowitt_barom_hpa Barometer
# TYPE ecowitt_barom_hpa gauge
ecowitt_barom_hpa{sensor="relative"} 1009.21
# HELP ecowitt_vpd_hpa Vapour pressure deficit
# TYPE ecowitt_vpd_hpa gauge
ecowitt_vpd_hpa 0.0
# HELP ecowitt_windspeed_kmh Wind speed
# TYPE ecowitt_windspeed_kmh gauge
# HELP ecowitt_rain_mm Rainfall
# TYPE ecowitt_rain_mm gauge
ecowitt_rain_mm{sensor="rate"} 0.0
ecowitt_rain_mm{sensor="event"} 0.0
ecowitt_rain_mm{sensor="hourly"} 0.0
ecowitt_rain_mm{sensor="daily"} 0.0
ecowitt_rain_mm{sensor="weekly"} 0.0
ecowitt_rain_mm{sensor="monthly"} 5.3
ecowitt_rain_mm{sensor="yearly"} 184.9
ecowitt_rain_mm{sensor="total"} 184.9
# HELP ecowitt_lightning_km Lightning distance
# TYPE ecowitt_lightning_km gauge
ecowitt_lightning_km 31.0
# HELP ecowitt_lightning_num Lightning daily count
# TYPE ecowitt_lightning_num gauge
ecowitt_lightning_num 0.0
# HELP ecowitt_wh90_volt WS90 electrical energy stored
# TYPE ecowitt_wh90_volt gauge
```

## Building and running locally
```
podman build -t ecowitt-exporter .
podman run -d --rm -p 8088:8088 -e DEBUG=yes ecowitt-exporter
```
