import os
import logging
from flask import Flask, request
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import make_wsgi_app, Gauge
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

app = Flask(__name__)

debug = os.environ.get('DEBUG', 'no') == 'yes'
temperature_unit = os.environ.get('TEMPERATURE_UNIT', 'c')
pressure_unit = os.environ.get('PRESSURE_UNIT', 'hpa')
wind_unit = os.environ.get('WIND_UNIT', 'kmh')
rain_unit = os.environ.get('RAIN_UNIT', 'mm')
distance_unit = os.environ.get('DISTANCE_UNIT', 'km')
irradiance_unit = os.environ.get('IRRADIANCE_UNIT', 'wm2')
influxdb_token = os.environ.get('INFLUXDB_TOKEN', None)
influxdb_url = os.environ.get('INFLUXDB_URL', 'http://localhost:8086/')
influxdb_org = os.environ.get('INFLUXDB_ORG', 'influxdata')
influxdb_bucket = os.environ.get('INFLUXDB_BUCKET', 'default')
station_id = os.environ.get('STATION_ID', 'ecowitt')
prometheus = os.environ.get('PROMETHEUS', 'yes') == 'yes'
influxdb = os.environ.get('INFLUXDB', 'no') == 'yes'

print ("Ecowitt Exporter")
print ("================")
print ("Configuration:")
print ('  DEBUG:            ' + str(debug))
print ('  TEMPERATURE_UNIT: ' + temperature_unit)
print ('  PRESSURE_UNIT:    ' + pressure_unit)
print ('  WIND_UNIT:        ' + wind_unit)
print ('  RAIN_UNIT:        ' + rain_unit)
print ('  DISTANCE_UNIT:    ' + distance_unit)
print ('  IRRADIANCE_UNIT:  ' + irradiance_unit)
print ('  INFLUXDB_TOKEN:   ' + str(influxdb_token))
print ('  INFLUXDB_URL:     ' + influxdb_url)
print ('  INFLUXDB_ORG:     ' + str(influxdb_org))
print ('  INFLUXDB_BUCKET:  ' + influxdb_bucket)
print ('  STATION_ID:       ' + station_id)
print ('  PROMETHEUS:       ' + str(prometheus))
print ('  INFLUXDB:         ' + str(influxdb))

@app.route('/')
def version():
    return "Ecowitt Exporter\n"


@app.before_request
def log_request_info():
    app.logger.debug('Headers: %s', request.headers)
    app.logger.debug('Body: %s', request.get_data())


def is_integer(element: any) -> bool:
    """
    Test if a string can be represent as an integer
    """
    if element is None: 
        return False
    try:
        int(element)
        return True
    except ValueError:
        return False


def is_float(element: any) -> bool:
    """
    Test if a string can be represent as a float
    """
    if element is None: 
        return False
    try:
        float(element)
        return True
    except ValueError:
        return False


def numify(value):
    """
    Convert a string to an integer or float if possible
    """
    if is_integer(value):
        return int(value)
    elif is_float(value):
        return float(value)
    else:
        return value


@app.route('/report', methods=['POST'])
def logecowitt():

    # Retrieve the POST body
    data = request.form

    # Set up a dict to receive the processed results
    results = {}

    for key in data:
        # Process each key from the raw data, do unit conversions if necessary,
        # then store the results in a new dict called results
        value = data[key]
        app.logger.debug("Received raw value %s: %s", key, value)

        # Ignore these fields
        if key in ['PASSKEY', 'stationtype', 'dateutc', 'wh25batt', 'batt1', 'batt2', 'freq', 'model', 'runtime']:
            continue

        # No conversions needed
        if key in ['humidity', 'humidityin', 'winddir', 'uv', 'pm25_ch1', 'pm25_avg_24h_ch1', 'pm25batt1', 'wh65batt', 'lightning_num']:
            results[key] = value

        # Solar irradiance, default W/m^2
        if key in ['solarradiation']:
            if irradiance_unit == 'lx':
                # Convert degrees W/m2 to lux
                irradiance_lx = float(value) / 0.0079
                value = "{:.2f}".format(irradiance_lx)
            elif irradiance_unit == 'fc':
                # Convert degrees W/m2 to foot candle
                irradiance_lx = float(value) * 6.345
                value = "{:.2f}".format(irradiance_lx)
            results[key] = value

        # Temperature, default Fahrenheit
        if key in ['tempinf', 'tempf', 'temp1f', 'temp2f', 'temp3f', 'temp4f', 'temp5f', 'temp6f', 'temp7f', 'temp8f']:
            if temperature_unit == 'c':
                # Convert degrees Fahrenheit to Celsius
                tempc = (float(value) - 32) * 5/9
                value = "{:.2f}".format(tempc)
            if temperature_unit == 'k':
                # Convert degrees Fahrenheit to Kelvin
                tempk = (float(value) - 32) * 5/9 + 273.15
                value = "{:.2f}".format(tempk)
            key = key[:-1]
            results[key] = value

        # Pressure, default inches Hg
        if key in ['baromrelin', 'baromabsin']:
            if pressure_unit == 'hpa':
                # Convert inches Hg to hPa
                pressurehpa = float(value) * 33.6585
                value = "{:.2f}".format(pressurehpa)
            if pressure_unit == 'mmhg':
                # Convert inches Hg to mmHg
                pressuremmhg = float(value) * 25.4
                value = "{:.2f}".format(pressuremmhg)
            key = key[:-2]
            results[key] = value

        # Wind speed, default mph
        if key in ['windspeedmph', 'windgustmph', 'maxdailygust']:
            if wind_unit == 'kmh':
                # Convert mph to km/h
                speedkmh = float(value) * 1.60934
                value = "{:.2f}".format(speedkmh)
            elif wind_unit == 'ms':
                # Convert mph to m/s
                speedms = float(value) / 2.237
                value = "{:.2f}".format(speedms)
            elif wind_unit == 'knots':
                # Convert mph to knots
                speedknots = float(value) / 1.151
                value = "{:.2f}".format(speedknots)
            elif wind_unit == 'fps':
                # Convert mph to fps
                speedfps = float(value) * 1.467
                value = "{:.2f}".format(speedfps)
            if key != 'maxdailygust':
                key = key[:-3]
            results[key] = value

        # Rainfall, default inches
        if key in ['rainratein', 'eventrainin', 'hourlyrainin', 'dailyrainin', 'weeklyrainin', 'monthlyrainin', 'yearlyrainin', 'totalrainin']:
            if rain_unit == 'mm':
                # Convert inches to mm
                rainmm = float(value) * 25.4
                value = "{:.1f}".format(rainmm)
            key = key[:-2]
            results[key] = value

        # Lightning distance, default kilometers
        if key in ['lightning']:
            if distance_unit == 'km':
                results[key] = value
            elif distance_unit == 'mi':
                # Convert km to miles
                distancemi = float(value) / 1.60934
                value = "{:.2f}".format(distancemi)
                results[key] = value

    # Now loop on our processed results and do things with them
    points = []
    for key, value in results.items():
        # Send the data to the Prometheus exporter
        if prometheus:
            metrics[key].set(value)
            app.logger.debug("Set Prometheus metric %s: %s", key, value)

        # Build an array of points to send to InfluxDB
        if influxdb:
            point = Point("weather").tag("station_id", station_id).field(key, numify(value))
            app.logger.debug("Created InfluxDB point %s: %s", key, value)
            points.append(point)

    # Send the data to InfluxDB
    if influxdb:
        with InfluxDBClient(url=influxdb_url, token=influxdb_token, org=influxdb_org) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket=influxdb_bucket, record=points)
            app.logger.debug("Submitted InfluxDB points to server")

    # Return a 200 to the weather station
    response = app.response_class(
            response='OK',
            status=200,
            mimetype='application/json'
    )
    return response

if __name__ == "__main__":

    # Set up various Prometheus metrics with descriptions and units
    metrics={}
    metrics['tempin'] = Gauge(name='tempin', documentation='Indoor temperature', unit=temperature_unit)
    metrics['temp'] = Gauge(name='temp', documentation='Outdoor temperature', unit=temperature_unit)
    metrics['temp1'] = Gauge(name='temp1', documentation='Temp 1', unit=temperature_unit)
    metrics['temp2'] = Gauge(name='temp2', documentation='Temp 2', unit=temperature_unit)
    metrics['temp3'] = Gauge(name='temp3', documentation='Temp 3', unit=temperature_unit)
    metrics['temp4'] = Gauge(name='temp4', documentation='Temp 4', unit=temperature_unit)
    metrics['temp5'] = Gauge(name='temp5', documentation='Temp 5', unit=temperature_unit)
    metrics['temp6'] = Gauge(name='temp6', documentation='Temp 6', unit=temperature_unit)
    metrics['temp7'] = Gauge(name='temp7', documentation='Temp 7', unit=temperature_unit)
    metrics['temp8'] = Gauge(name='temp8', documentation='Temp 8', unit=temperature_unit)
    metrics['humidity'] = Gauge(name='humidity', documentation='Outdoor humidity', unit='percent')
    metrics['humidityin'] = Gauge(name='humidityin', documentation='Indoor humidity', unit='percent')
    metrics['winddir'] = Gauge(name='winddir', documentation='Wind direction', unit='degree')
    metrics['uv'] = Gauge(name='uv', documentation='UV index')
    metrics['pm25_ch1'] = Gauge(name='pm25', documentation='PM2.5')
    metrics['pm25_avg_24h_ch1'] = Gauge(name='pm25_avg_24h', documentation='PM2.5 24-hour average')
    metrics['pm25batt1'] = Gauge(name='pm25batt', documentation='PM2.5 sensor battery')
    metrics['wh65batt'] = Gauge(name='wh65batt', documentation='Weather station battery status')
    metrics['solarradiation'] = Gauge(name='solarradiation', documentation='Solar irradiance', unit='wm2')
    metrics['baromrel'] = Gauge(name='baromrel', documentation='Relative barometer', unit=pressure_unit)
    metrics['baromabs'] = Gauge(name='baromabs', documentation='Absolute barometer', unit=pressure_unit)
    metrics['windspeed'] = Gauge(name='windspeed', documentation='Wind speed', unit=wind_unit)
    metrics['windgust'] = Gauge(name='windgust', documentation='Wind gust', unit=wind_unit)
    metrics['maxdailygust'] = Gauge(name='maxdailygust', documentation='Max daily gust', unit=wind_unit)
    metrics['rainrate'] = Gauge(name='rainrate', documentation='Rainfall rate', unit=rain_unit)
    metrics['eventrain'] = Gauge(name='eventrain', documentation='Event rainfall', unit=rain_unit)
    metrics['hourlyrain'] = Gauge(name='hourlyrain', documentation='Hourly rainfall', unit=rain_unit)
    metrics['dailyrain'] = Gauge(name='dailyrain', documentation='Daily rainfall', unit=rain_unit)
    metrics['weeklyrain'] = Gauge(name='weeklyrain', documentation='Weekly rainfall', unit=rain_unit)
    metrics['monthlyrain'] = Gauge(name='monthlyrain', documentation='Monthly rainfall', unit=rain_unit)
    metrics['yearlyrain'] = Gauge(name='yearlyrain', documentation='Yearly rainfall', unit=rain_unit)
    metrics['totalrain'] = Gauge(name='totalrain', documentation='Total rainfall', unit=rain_unit)
    metrics['lightning'] = Gauge(name='lightning', documentation='Lightning distance', unit=distance_unit)
    metrics['lightning_num'] = Gauge(name='lightning_num', documentation='Lightning daily count')

    # Increase Flask logging if in debug mode
    if debug:
        app.logger.setLevel(logging.DEBUG)

    # Add prometheus wsgi middleware to route /metrics requests
    if prometheus:
        app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
            '/metrics': make_wsgi_app()
        })
    app.run(host="0.0.0.0", port=8088, debug=debug)
