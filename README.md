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
- WH51 Soil Moisture Meter

## Note about Ecowitt firmware

It seems that an Ecowitt WS2910 with firmware v5.1.1 has a bug when writing out HTTP headers, which causes it to not work with Flask.
This [has been reported](https://github.com/pallets/werkzeug/issues/2734) to Flask, but closed as WONTFIX because the underlying problem
is with the Ecowitt firmware.

It is possible to work around this issue by fronting this exporter with an NGINX reverse proxy (such as a Kubernetes Ingress),
because NGINX magically fixes the headers on the fly.

## Environment variables

Set the units for the export of each metric. Ecowitt weather stations return readings in a mixture of Metric
and Imperial units. This exporter converts them on the fly if necessary, to present them to Prometheus in
your desired format. Metric/SI is always the default. People in the USA will probably want to set everything
to Imperial alternatives, while Brits will likely want a mixture of both!

All units are expressed using their IDs in the
[Grafana spec](https://github.com/grafana/grafana/blob/main/packages/grafana-data/src/valueFormats/categories.ts).
Units not natively supported by Grafana are not supported here.

| Variable           | Default       | Choices                                                    | Meaning                |
|--------------------|---------------|------------------------------------------------------------|------------------------|
| `DEBUG`            | `no`          | `no`, `yes`                                                | Enable extra output for debugging |
| `TEMPERATURE_UNIT` | `celsius`     | `celsius`, `fahrenheit`, `kelvin`                          | Temperature in Celsius, Fahrenheit or Kelvin |
| `PRESSURE_UNIT`    | `pressurehpa` | `pressurehpa`, `pressurehg`                                | Pressure in hectopascals (millibars) or inches of mercury |
| `WIND_UNIT`        | `velocitykmh` | `velocitykmh`, `velocitymph`, `velocityms`, `velocityknot` | Speed in km/hour, miles/hour, metres/second, or knots |
| `RAIN_UNIT`        | `lengthmm`    | `lengthmm`, `lengthin`                                     | Rainfall in millimetres or inches |
| `IRRADIANCE_UNIT`  | `Wm2`         | `Wm2`, `lux`                                               | Solar irradiance in Watts/m^2 or Lux |
| `DISTANCE_UNIT`    | `lengthkm`    | `lengthkm`, `lengthmi`                                     | Distance from the last lightning in kilometers or miles |
| `AQI_STANDARD`     | `uk`          | `uk`, `epa`, `mep`, `nepm`                                 | Air Quality Index standard in UK DAQI, US EPA, China MEP, Australia NEPM |

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
ecowitt_stationtype_info{stationtype="GW1100A_V2.4.1"} 1.0
# HELP ecowitt_freq_info Ecowitt radio frequency
# TYPE ecowitt_freq_info gauge
ecowitt_freq_info{freq="868M"} 1.0
# HELP ecowitt_model_info Ecowitt model
# TYPE ecowitt_model_info gauge
ecowitt_model_info{model="GW1100A"} 1.0
# HELP ecowitt_temp Temperature
# TYPE ecowitt_temp gauge
ecowitt_temp{sensor="indoor",unit="c"} 30.1
ecowitt_temp{sensor="outdoor",unit="c"} 17.7
ecowitt_temp{sensor="ch1",unit="c"} 23.5
ecowitt_temp{sensor="ch2",unit="c"} 21.7
ecowitt_temp{sensor="ch3",unit="c"} 24.4
ecowitt_temp{sensor="ch4",unit="c"} 22.8
ecowitt_temp{sensor="ch5",unit="c"} 24.3
ecowitt_temp{sensor="ch6",unit="c"} 25.4
ecowitt_temp{sensor="ch8",unit="c"} 23.3
# HELP ecowitt_humidity Relative humidity
# TYPE ecowitt_humidity gauge
ecowitt_humidity{sensor="indoor",unit="percent"} 41.0
ecowitt_humidity{sensor="outdoor",unit="percent"} 75.0
ecowitt_humidity{sensor="ch1",unit="percent"} 57.0
ecowitt_humidity{sensor="ch2",unit="percent"} 61.0
ecowitt_humidity{sensor="ch3",unit="percent"} 54.0
ecowitt_humidity{sensor="ch4",unit="percent"} 62.0
ecowitt_humidity{sensor="ch5",unit="percent"} 54.0
ecowitt_humidity{sensor="ch6",unit="percent"} 45.0
ecowitt_humidity{sensor="ch8",unit="percent"} 58.0
# HELP ecowitt_winddir Wind direction
# TYPE ecowitt_winddir gauge
ecowitt_winddir 173.0
# HELP ecowitt_uv UV index
# TYPE ecowitt_uv gauge
ecowitt_uv 0.0
# HELP ecowitt_pm25 PM2.5 concentration
# TYPE ecowitt_pm25 gauge
ecowitt_pm25{sensor="ch2",series="realtime"} 3.0
ecowitt_pm25{sensor="ch2",series="avg_24h"} 2.6
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
ecowitt_batteryvoltage{sensor="soilbatt1"} 1.7
# HELP ecowitt_solarradiation Solar irradiance
# TYPE ecowitt_solarradiation gauge
ecowitt_solarradiation{unit="wm2"} 29.22
# HELP ecowitt_barom Barometer
# TYPE ecowitt_barom gauge
ecowitt_barom{sensor="relative",unit="hpa"} 1008.6
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
