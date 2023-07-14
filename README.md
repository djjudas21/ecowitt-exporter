# ecowitt-exporter

Ecowitt exporter for Prometheus & InfluxDB

The WiFi-enabled Ecowitt weather stations can export metrics in a number of protocols to various online weather services, as a push operation.
They also support pushing to a custom endpoint in a choice of two protocols, Ecowitt or Wunderground. Blogger Ernest Neijenhuis has
[checked out the protocols](https://www.pa3hcm.nl/?p=2095) and found that the Ecowitt protocol is more comprehensive. He then wrote a Python
app called [Ecowither](https://github.com/pa3hcm/ecowither) to gateway the Ecowitt metrics into InfluxDB.

Here I am building on his work to present the Ecowitt metrics as an exporter for Prometheus.

This exporter runs on a single HTTP port (default `8088`) and provides two endpoints:

* `/report` where the Ecowitt weather station should POST its data
* `/metrics` where Prometheus can scrape metrics with a GET request

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

| Variable           | Default                  | Choices                            | Meaning                                                                  |
|--------------------|--------------------------|------------------------------------|--------------------------------------------------------------------------|
| `DEBUG`            | `no`                     | `no`, `yes`                        | Enable extra output for debugging                                        |
| `PROMETHEUS`       | `yes`                    | `no`, `yes`                        | Enable Prometheus exporter                                               |
| `INFLUXDB`         | `no`                     | `no`, `yes`                        | Enable InfluxDB support                                                  |
| `TEMPERATURE_UNIT` | `c`                      | `c`, `f`, `k`                      | Temperature in Celsius, Fahrenheit or Kelvin                             |
| `PRESSURE_UNIT`    | `hpa`                    | `hpa`, `in`, `mmhg`                | Pressure in hectopascals (millibars), inches of mercury or mm of mercury |
| `WIND_UNIT`        | `kmh`                    | `kmh`, `mph`, `ms`, `knots`, `fps` | Speed in km/hour, miles/hour, metres/second, knots or feet/second        |
| `RAIN_UNIT`        | `mm`                     | `mm`, `in`                         | Rainfall in millimetres or inches                                        |
| `IRRADIANCE_UNIT`  | `wm2`                    | `wm2`, `lx`, `fc`                  | Solar irradiance in Watts/m^2                                            |
| `INFLUXDB_TOKEN`   |                          |                                    | InfluxDB token                                                           |
| `INFLUXDB_URL`     | `http://localhost:8086/` |                                    | InfluxDB endpoint                                                        |
| `INFLUXDB_ORG`     | `influxdata`             |                                    | InfluxDB organisation                                                    |
| `INFLUXDB_BUCKET`  | `default`                |                                    | InfluxDB bucket                                                          |

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

Real data captured from the Ecowitt weather station with [http-webhook](https://artifacthub.io/packages/helm/securecodebox/http-webhook) to be used as a test:

```json
{
    "path": "/report",
    "headers": {
        "host": "192.168.0.65",
        "connection": "Close",
        "content-type": "application/x-www-form-urlencoded",
        "content-length": "493"
    },
    "method": "POST",
    "body": "PASSKEY=573AF40DB42C66057D20631F706CD585&stationtype=EasyWeatherPro_V5.1.1&runtime=1&dateutc=2023-06-20+14:56:02&tempinf=73.4&humidityin=49&baromrelin=29.917&baromabsin=29.536&tempf=72.5&humidity=58&winddir=251&windspeedmph=1.12&windgustmph=2.24&maxdailygust=9.17&solarradiation=293.99&uv=2&rainratein=0.000&eventrainin=0.638&hourlyrainin=0.000&dailyrainin=0.638&weeklyrainin=0.650&monthlyrainin=0.650&yearlyrainin=0.650&totalrainin=0.650&wh65batt=0&freq=868M&model=WS2900_V2.01.18&interval=60",
    "fresh": false,
    "hostname": "192.168.0.65",
    "ip": "::ffff:10.1.199.64",
    "ips": [],
    "protocol": "http",
    "query": {},
    "subdomains": [],
    "xhr": false,
    "os": {
        "hostname": "http-webhook-6675856576-j2jzb"
    },
    "connection": {}
}
```

This POST request can be simulated with curl:

```
curl -d "PASSKEY=573AF40DB42C66057D20631F706CD585&stationtype=EasyWeatherPro_V5.1.1&runtime=1&dateutc=2023-06-20+14:56:02&tempinf=73.4&humidityin=49&baromrelin=29.917&baromabsin=29.536&tempf=72.5&humidity=58&winddir=251&windspeedmph=1.12&windgustmph=2.24&maxdailygust=9.17&solarradiation=293.99&uv=2&rainratein=0.000&eventrainin=0.638&hourlyrainin=0.000&dailyrainin=0.638&weeklyrainin=0.650&monthlyrainin=0.650&yearlyrainin=0.650&totalrainin=0.650&wh65batt=0&freq=868M&model=WS2900_V2.01.18&interval=60" -X POST http://192.168.0.65:8080/report
```

We can then view the corresponding Prometheus metrics with a simple GET request (output has been truncated because it is very long):

```
curl http://localhost:8088/metrics
# HELP tempin_c Indoor temperature
# TYPE tempin_c gauge
tempin_c 18.89
# HELP temp_c Outdoor temperature
# TYPE temp_c gauge
temp_c 8.78
# HELP humidity_percent Outdoor humidity
# TYPE humidity_percent gauge
humidity_percent 91.0
# HELP humidityin_percent Indoor humidity
# TYPE humidityin_percent gauge
humidityin_percent 51.0
# HELP winddir_degree Wind direction
# TYPE winddir_degree gauge
winddir_degree 261.0
# HELP uv UV index
# TYPE uv gauge
uv 0.0
# HELP solarradiation_wm2 Solar irradiance
# TYPE solarradiation_wm2 gauge
solarradiation_wm2 57.25
# HELP baromrel_hpa Relative barometer
# TYPE baromrel_hpa gauge
baromrel_hpa 995.11
# HELP baromabs_hpa Absolute barometer
# TYPE baromabs_hpa gauge
baromabs_hpa 995.11
# HELP windspeed_kmh Wind speed
# TYPE windspeed_kmh gauge
windspeed_kmh 14.4
# HELP windgust_kmh Wind gust
# TYPE windgust_kmh gauge
windgust_kmh 23.75
# HELP maxdailygust_kmh Max daily gust
# TYPE maxdailygust_kmh gauge
maxdailygust_kmh 34.92
# HELP rainrate_mm Rainfall rate
# TYPE rainrate_mm gauge
rainrate_mm 0.0
# HELP eventrain_mm Event rainfall
# TYPE eventrain_mm gauge
eventrain_mm 1.8
# HELP hourlyrain_mm Hourly rainfall
# TYPE hourlyrain_mm gauge
hourlyrain_mm 0.0
# HELP dailyrain_mm Daily rainfall
# TYPE dailyrain_mm gauge
dailyrain_mm 0.3
# HELP weeklyrain_mm Weekly rainfall
# TYPE weeklyrain_mm gauge
weeklyrain_mm 2.8
# HELP monthlyrain_mm Monthly rainfall
# TYPE monthlyrain_mm gauge
monthlyrain_mm 36.1
# HELP yearlyrain_mm Yearly rainfall
# TYPE yearlyrain_mm gauge
yearlyrain_mm 616.1
# HELP totalrain_mm Total rainfall
# TYPE totalrain_mm gauge
totalrain_mm 616.1
```
