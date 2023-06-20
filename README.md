# ecowitt-exporter

Ecowitt exporter for Prometheus

The WiFi-enabled Ecowitt weather stations can export metrics in a number of protocols to various online weather services, as a push operation.
They also support pushing to a custom endpoint in a choice of two protocols, Ecowitt or Wunderground. Blogger Ernest Neijenhuis has
[checked out the protocols](https://www.pa3hcm.nl/?p=2095) and found that the Ecowitt protocol is more comprehensive. He then wrote a Python
app called [Ecowither](https://github.com/pa3hcm/ecowither) to gateway the Ecowitt metrics into InfluxDB.

Here I am building on his work to present the Ecowitt metrics as an exporter for Prometheus.

This exporter runs on a single HTTP port (default `8088`) and provides two endpoints:

* `/report` where the Ecowitt weather station should POST its data
* `/metrics` where Prometheus can scape metrics with a GET request

## Environment variables

Set the units for the export of each metric. Ecowitt weather stations always take measurements in Imperial.
This exporter converts them on the fly if necessary, to present them to Prometheus in your desired format.
Metric/SI is always the default. People in the USA will probably want to set everything to Imperial
alternatives, while Brits will likely want a mixture of both!

All units are expressed in lower case and without slashes, for simplicity. Apologies to scientists,
for whom this will be a difficult time.

| Variable           | Default | Choices         | Meaning                                       | Not yet supported           |
|--------------------|---------|-----------------|-----------------------------------------------|-----------------------------|
| `DEBUG`            | `FALSE` | `FALSE`, `TRUE` | Enable extra output for debugging             |                             |
| `TEMPERATURE_UNIT` | `c`     | `c`, `f`        | Temperature in Celcius or Fahrenheit          |                             |
| `PRESSURE_UNIT`    | `hpa`   | `hpa`, `in`     | Pressure in Hectopascals or inches of mercury | `mmhg`                      |
| `WIND_UNIT`        | `kmh`   | `kmh`, `mph`    | Speed in kilometres/hour or miles/hour        | `ms`, `knots`, `fpm`, `bft` |
| `RAIN_UNIT`        | `mm`    | `mm`, `in`      | Rainfall in millimetres or inches             |                             |
| `IRRADIANCE_UNIT`  | `wm2`   | `wm2`           | Solar irradiance in Watts/m^2                 | `lx`, `fc`                  |

## How to configure your weather station

## Testing

Example data sent from the Ecowitt weather station via a POST request can be simulated with curl:

```
curl -d "tempinf=78.6&humidityin=46&baromrelin=29.955&baromabsin=29.574&tempf=71.8&humidity=50&winddir=186&windspeedmph=2.01&windgustmph=3.36&maxdailygust=13.65&solarradiation=50.32&uv=0&rainratein=0.000&eventrainin=0.000&hourlyrainin=0.000&dailyrainin=0.000&weeklyrainin=0.012&monthlyrainin=0.012&yearlyrainin=0.012&totalrainin=0.012" -X POST http://localhost:8088/report
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
