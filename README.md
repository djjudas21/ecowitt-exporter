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

| Variable           | Default | Choices         | Meaning                                       | Not yet supported           |
|--------------------|---------|-----------------|-----------------------------------------------|-----------------------------|
| `DEBUG`            | `FALSE` | `FALSE`, `TRUE` | Enable extra output for debugging             |                             |

## How to configure your weather station

## Testing

Example data sent from the Ecowitt weather station via a POST request can be simulated with curl:

```
curl -d "tempinf=78.6&humidityin=46&baromrelin=29.955&baromabsin=29.574&tempf=71.8&humidity=50&winddir=186&windspeedmph=2.01&windgustmph=3.36&maxdailygust=13.65&solarradiation=50.32&uv=0&rainratein=0.000&eventrainin=0.000&hourlyrainin=0.000&dailyrainin=0.000&weeklyrainin=0.012&monthlyrainin=0.012&yearlyrainin=0.012&totalrainin=0.012" -X POST http://localhost:8088/report
```

We can then view the corresponding Prometheus metrics with a simple GET request (output has been truncated because it is very long):

```
curl http://localhost:8088/metrics
# HELP tempinf_f temps
# TYPE tempinf_f gauge
tempinf_f 66.0
# HELP tempf_f tempf
# TYPE tempf_f gauge
tempf_f 47.8
# HELP temp1f_f temp1f
# TYPE temp1f_f gauge
temp1f_f 49.46
# HELP temp2f_f temp2f
# TYPE temp2f_f gauge
temp2f_f 63.5
# HELP tempinc_c temps
# TYPE tempinc_c gauge
tempinc_c 18.89
# HELP tempc_c tempf
# TYPE tempc_c gauge
tempc_c 8.78
# HELP temp1c_c temp1f
# TYPE temp1c_c gauge
temp1c_c 9.7
# HELP temp2c_c temp2f
# TYPE temp2c_c gauge
temp2c_c 17.5
```
