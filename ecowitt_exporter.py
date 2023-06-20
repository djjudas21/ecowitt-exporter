from flask import Flask, request
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import make_wsgi_app, Gauge
import os

app = Flask(__name__)

station_id = os.environ.get('STATION_ID', 'my-station')

print ("Ecowitt Exporter v0.1")
print ("==============")
print ("Configuration:")
print ("  STATION_ID:      " + station_id)


@app.route('/')
def version():
    return "Ecowitt Exporter v0.1\n"


@app.route('/report', methods=['POST'])
def logEcowitt():

    for key in request.form:
        value = request.form[key]

        # Ignore these fields
        if key in ['PASSKEY', 'stationtype', 'dateutc', 'wh65batt', 'wh25batt', 'batt1', 'batt2', 'freq', 'model', 'runtime']:
            continue

        # No conversions needed
        if key in ['humidity', 'humidityin', 'winddir', 'uv', 'solarradiation']:
            generic[key].set(value)

        # Convert degrees Fahrenheit to Celsius
        if key in ['tempinf', 'tempf', 'temp1f', 'temp2f', 'temp3f', 'temp4f', 'temp5f', 'temp6f', 'temp7f', 'temp8f']:
            tempC = (float(value) - 32) * 5/9
            valueC = "{:.2f}".format(tempC)
            keyC = key[:-1] + 'c'
            temperature[key].set(value)
            temperature[keyC].set(valueC)

        # Convert pressure inches to hPa
        if key in ['baromrelin', 'baromabsin']:
            pressureHpa = float(value) * 33.6585
            valueHpa = "{:.2f}".format(pressureHpa)
            keyHpa = key[:-2] + 'hpa'
            pressure[key].set(value)
            pressure[keyHpa].set(valueHpa)

        # Convert speed mph to km/h
        if key in ['windspeedmph', 'windgustmph', 'maxdailygust']:
            speedkmh = float(value) * 1.60934
            valuekmh = "{:.2f}".format(speedkmh)
            if key == 'maxdailygust':
                keykmh = key + 'kmh'
            else:
                keykmh = key[:-3] + 'kmh'
            wind[key].set(value)
            wind[keykmh].set(valuekmh)

        # Convert rain inches to mm
        if key in ['rainratein', 'eventrainin', 'hourlyrainin', 'dailyrainin', 'weeklyrainin', 'monthlyrainin', 'yearlyrainin', 'totalrainin']:
            mm = float(value) * 25.4
            valuemm = "{:.1f}".format(mm)
            keymm = key[:-2] + 'mm'
            rain[key].set(value)
            rain[keymm].set(valuemm)

    response = app.response_class(
            response='OK',
            status=200,
            mimetype='application/json'
    )
    return response

if __name__ == "__main__":

    # Set up various Prometheus metrics with descriptions and units
    temperature={}
    temperature['tempinf'] = Gauge(name='tempinf', documentation='temps', unit='f')
    temperature['tempf'] = Gauge(name='tempf', documentation='tempf', unit='f')
    temperature['temp1f'] = Gauge(name='temp1f', documentation='temp1f', unit='f')
    temperature['temp2f'] = Gauge(name='temp2f', documentation='temp2f', unit='f')
    temperature['temp3f'] = Gauge(name='temp3f', documentation='temp3f', unit='f')
    temperature['temp4f'] = Gauge(name='temp4f', documentation='temp4f', unit='f')
    temperature['temp5f'] = Gauge(name='temp5f', documentation='temp5f', unit='f')
    temperature['temp6f'] = Gauge(name='temp6f', documentation='temp6f', unit='f')
    temperature['temp7f'] = Gauge(name='temp7f', documentation='temp7f', unit='f')
    temperature['temp8f'] = Gauge(name='temp8f', documentation='temp8f', unit='f')
    temperature['tempinc'] = Gauge(name='tempinc', documentation='temps', unit='c')
    temperature['tempc'] = Gauge(name='tempc', documentation='tempf', unit='c')
    temperature['temp1c'] = Gauge(name='temp1c', documentation='temp1f', unit='c')
    temperature['temp2c'] = Gauge(name='temp2c', documentation='temp2f', unit='c')
    temperature['temp3c'] = Gauge(name='temp3c', documentation='temp3f', unit='c')
    temperature['temp4c'] = Gauge(name='temp4c', documentation='temp4f', unit='c')
    temperature['temp5c'] = Gauge(name='temp5c', documentation='temp5f', unit='c')
    temperature['temp6c'] = Gauge(name='temp6c', documentation='temp6f', unit='c')
    temperature['temp7c'] = Gauge(name='temp7c', documentation='temp7f', unit='c')
    temperature['temp8c'] = Gauge(name='temp8c', documentation='temp8f', unit='c')

    generic={}
    generic['humidity'] = Gauge(name='humidity', documentation='humidity', unit='percent')
    generic['humidityin'] = Gauge(name='humidityin', documentation='humidityin', unit='percent')
    generic['winddir'] = Gauge(name='winddir', documentation='winddir', unit='degree')
    generic['uv'] = Gauge(name='uv', documentation='uv')
    generic['solarradiation'] = Gauge(name='solarradiation', documentation='Solar radiation', unit='klux')

    pressure={}
    pressure['baromrelin'] = Gauge(name='baromrelin', documentation='baromrelin', unit='in')
    pressure['baromabsin'] = Gauge(name='baromabsin', documentation='baromabsin', unit='in')
    pressure['baromrelhpa'] = Gauge(name='baromrelhpa', documentation='baromrelhpa', unit='hpa')
    pressure['baromabshpa'] = Gauge(name='baromabshpa', documentation='baromabshpa', unit='hpa')

    wind={}
    wind['windspeedmph'] = Gauge(name='windspeedmph', documentation='windspeedmph', unit='mph')
    wind['windgustmph'] = Gauge(name='windgustmph', documentation='windgustmph', unit='mph')
    wind['maxdailygust'] = Gauge(name='maxdailygustmph', documentation='maxdailygustmph', unit='mph')
    wind['windspeedkmh'] = Gauge(name='windspeedkmh', documentation='windspeedkmh', unit='kmh')
    wind['windgustkmh'] = Gauge(name='windgustkmh', documentation='windgustkmh', unit='kmh')
    wind['maxdailygustkmh'] = Gauge(name='maxdailygustkmh', documentation='maxdailygustkmh', unit='kmh')

    rain={}
    rain['rainratein'] = Gauge(name='rainratein', documentation='rainratein', unit='in')
    rain['eventrainin'] = Gauge(name='eventrainin', documentation='eventrainin', unit='in')
    rain['hourlyrainin'] = Gauge(name='hourlyrainin', documentation='hourlyrainin', unit='in')
    rain['dailyrainin'] = Gauge(name='dailyrainin', documentation='dailyrainin', unit='in')
    rain['weeklyrainin'] = Gauge(name='weeklyrainin', documentation='weeklyrainin', unit='in')
    rain['monthlyrainin'] = Gauge(name='monthlyrainin', documentation='monthlyrainin', unit='in')
    rain['yearlyrainin'] = Gauge(name='yearlyrainin', documentation='yearlyrainin', unit='in')
    rain['totalrainin'] = Gauge(name='totalrainin', documentation='totalrainin', unit='in')
    rain['rainratemm'] = Gauge(name='rainratemm', documentation='rainratemm', unit='mm')
    rain['eventrainmm'] = Gauge(name='eventrainmm', documentation='eventrainmm', unit='mm')
    rain['hourlyrainmm'] = Gauge(name='hourlyrainmm', documentation='hourlyrainmm', unit='mm')
    rain['dailyrainmm'] = Gauge(name='dailyrainmm', documentation='dailyrainmm', unit='mm')
    rain['weeklyrainmm'] = Gauge(name='weeklyrainmm', documentation='weeklyrainmm', unit='mm')
    rain['monthlyrainmm'] = Gauge(name='monthlyrainmm', documentation='monthlyrainmm', unit='mm')
    rain['yearlyrainmm'] = Gauge(name='yearlyrainmm', documentation='yearlyrainmm', unit='mm')
    rain['totalrainmm'] = Gauge(name='totalrainmm', documentation='totalrainmm', unit='mm')

    # Add prometheus wsgi middleware to route /metrics requests
    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
        '/metrics': make_wsgi_app()
    })
    app.run(host="0.0.0.0", port=8088, debug=True)
