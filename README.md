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

## How to configure your weather station

## Testing

Example data sent from the Ecowitt weather station via a POST request can be simulated with curl:

```
curl -d "tempinf=66.0&humidityin=51&baromrelin=29.565&baromabsin=29.565&tempf=47.8&humidity=91&winddir=261&windspeedmph=8.95&windgustmph=14.76&maxdailygust=21.70&solarradiation=57.25&uv=0&rainratein=0.000&eventrainin=0.071&hourlyrainin=0.000&dailyrainin=0.012&weeklyrainin=0.110&monthlyrainin=1.421&yearlyrainin=24.256&totalrainin=24.256&temp1f=49.46&humidity1=98&temp2f=63.50&humidity2=51&wh65batt=0&wh25batt=0&batt1=0&batt2=0&freq=868M&model=WH2650" -X POST http://localhost:8088/report
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
