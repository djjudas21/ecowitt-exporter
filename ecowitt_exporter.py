from flask import Flask, request
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import make_wsgi_app, Gauge
import os

app = Flask(__name__)

debug = os.environ.get('DEBUG', None)
temperature_unit = os.environ.get('TEMPERATURE_UNIT', 'c')
pressure_unit = os.environ.get('PRESSURE_UNIT', 'hpa')
wind_unit = os.environ.get('WIND_UNIT', 'kmh')
rain_unit = os.environ.get('RAIN_UNIT', 'mm')
irradiance_unit = os.environ.get('IRRADIANCE_UNIT', 'wm2')

print ("Ecowitt Exporter v0.1")
print ("==============")
print ("Configuration:")
print ('  DEBUG:            ' + debug)
print ('  TEMPERATURE_UNIT: ' + temperature_unit)
print ('  PRESSURE_UNIT:    ' + pressure_unit)
print ('  WIND_UNIT:        ' + wind_unit)
print ('  RAIN_UNIT:        ' + rain_unit)
print ('  IRRADIANCE_UNIT:  ' + irradiance_unit)


@app.route('/')
def version():
    return "Ecowitt Exporter v0.1\n"


@app.route('/report', methods=['POST'])
def logEcowitt():

    # Retrieve the POST body
    data = request.form

    if debug:
        print('HEADERS')
        print(request.headers)
        body = request.get_data(as_text=True)
        print('BODY')
        print(body)
        print('FORM DATA')
        print(data)

    for key in data:
        value = data[key]

        if debug:
            print(f"  Received raw value {key}: {value}")

        # Ignore these fields
        if key in ['PASSKEY', 'stationtype', 'dateutc', 'wh65batt', 'wh25batt', 'batt1', 'batt2', 'freq', 'model', 'runtime']:
            continue

        # No conversions needed
        if key in ['humidity', 'humidityin', 'winddir', 'uv']:
            generic[key].set(value)

        # Solar irradiance
        if key in ['solarradiation']:
            irradiance[key].set(value)

        # Convert degrees Fahrenheit to Celsius
        if key in ['tempinf', 'tempf', 'temp1f', 'temp2f', 'temp3f', 'temp4f', 'temp5f', 'temp6f', 'temp7f', 'temp8f']:
            if temperature_unit == 'c':
                tempC = (float(value) - 32) * 5/9
                value = "{:.2f}".format(tempC)
            key = key[:-1]
            temperature[key].set(value)

        # Convert pressure inches to hPa
        if key in ['baromrelin', 'baromabsin']:
            if pressure_unit == 'hpa':
                pressurehpa = float(value) * 33.6585
                value = "{:.2f}".format(pressurehpa)
            key = key[:-2]
            pressure[key].set(value)

        # Convert speed mph to km/h
        if key in ['windspeedmph', 'windgustmph', 'maxdailygust']:
            if wind_unit == 'kmh':
                speedkmh = float(value) * 1.60934
                value = "{:.2f}".format(speedkmh)
            if key != 'maxdailygust':
                key = key[:-3]
            wind[key].set(value)

        # Convert rain inches to mm
        if key in ['rainratein', 'eventrainin', 'hourlyrainin', 'dailyrainin', 'weeklyrainin', 'monthlyrainin', 'yearlyrainin', 'totalrainin']:
            if rain_unit == 'mm':
                mm = float(value) * 25.4
                value = "{:.1f}".format(mm)
            key = key[:-2]
            rain[key].set(value)

    response = app.response_class(
            response='OK',
            status=200,
            mimetype='application/json'
    )
    return response

if __name__ == "__main__":

    # Set up various Prometheus metrics with descriptions and units
    temperature={}
    temperature['tempin'] = Gauge(name='tempin', documentation='Indoor temperature', unit=temperature_unit)
    temperature['temp'] = Gauge(name='temp', documentation='Outdoor temperature', unit=temperature_unit)
    temperature['temp1'] = Gauge(name='temp1', documentation='Temp 1', unit=temperature_unit)
    temperature['temp2'] = Gauge(name='temp2', documentation='Temp 2', unit=temperature_unit)
    temperature['temp3'] = Gauge(name='temp3', documentation='Temp 3', unit=temperature_unit)
    temperature['temp4'] = Gauge(name='temp4', documentation='Temp 4', unit=temperature_unit)
    temperature['temp5'] = Gauge(name='temp5', documentation='Temp 5', unit=temperature_unit)
    temperature['temp6'] = Gauge(name='temp6', documentation='Temp 6', unit=temperature_unit)
    temperature['temp7'] = Gauge(name='temp7', documentation='Temp 7', unit=temperature_unit)
    temperature['temp8'] = Gauge(name='temp8', documentation='Temp 8', unit=temperature_unit)

    generic={}
    generic['humidity'] = Gauge(name='humidity', documentation='Outdoor humidity', unit='percent')
    generic['humidityin'] = Gauge(name='humidityin', documentation='Indoor humidity', unit='percent')
    generic['winddir'] = Gauge(name='winddir', documentation='Wind direction', unit='degree')
    generic['uv'] = Gauge(name='uv', documentation='UV index')
    
    irradiance={}
    irradiance['solarradiation'] = Gauge(name='solarradiation', documentation='Solar irradiance', unit='wm2')

    pressure={}
    pressure['baromrel'] = Gauge(name='baromrel', documentation='Relative barometer', unit=pressure_unit)
    pressure['baromabs'] = Gauge(name='baromabs', documentation='Absolute barometer', unit=pressure_unit)

    wind={}
    wind['windspeed'] = Gauge(name='windspeed', documentation='Wind speed', unit=wind_unit)
    wind['windgust'] = Gauge(name='windgust', documentation='Wind gust', unit=wind_unit)
    wind['maxdailygust'] = Gauge(name='maxdailygust', documentation='Max daily gust', unit=wind_unit)

    rain={}
    rain['rainrate'] = Gauge(name='rainrate', documentation='Rainfall rate', unit=rain_unit)
    rain['eventrain'] = Gauge(name='eventrain', documentation='Event rainfall', unit=rain_unit)
    rain['hourlyrain'] = Gauge(name='hourlyrain', documentation='Hourly rainfall', unit=rain_unit)
    rain['dailyrain'] = Gauge(name='dailyrain', documentation='Daily rainfall', unit=rain_unit)
    rain['weeklyrain'] = Gauge(name='weeklyrain', documentation='Weekly rainfall', unit=rain_unit)
    rain['monthlyrain'] = Gauge(name='monthlyrain', documentation='Monthly rainfall', unit=rain_unit)
    rain['yearlyrain'] = Gauge(name='yearlyrain', documentation='Yearly rainfall', unit=rain_unit)
    rain['totalrain'] = Gauge(name='totalrain', documentation='Total rainfall', unit=rain_unit)

    # Add prometheus wsgi middleware to route /metrics requests
    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
        '/metrics': make_wsgi_app()
    })
    app.run(host="0.0.0.0", port=8088)
