from flask import Flask, request
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import make_wsgi_app
import os

app = Flask(__name__)

station_id = os.environ.get('STATION_ID', 'my-station')

print ("Ecowitt Exporter v0.1")
print ("==============")
print ("Configuration:")
print ("  STATION_ID:      " + station_id)


@app.route('/')
def version():
    return "Ecowither v0.1\n"


@app.route('/log/ecowitt', methods=['POST'])
def logEcowitt():
    fields = ''

    for field in request.get_data(as_text=True).split('&'):
        [key, value] = field.split('=')

        # Ignore these fields
        if key in ['PASSKEY', 'stationtype', 'dateutc', 'wh65batt', 'wh25batt', 'batt1', 'batt2', 'freq', 'model']:
            continue

        # Convert degrees Fahrenheit to Celsius
        if key in ['tempinf', 'tempf', 'temp1f', 'temp2f', 'temp3f', 'temp4f', 'temp5f', 'temp6f', 'temp7f', 'temp8f']:
            tempC = (float(value) - 32) * 5/9
            value = "{:.2f}".format(tempC)
            key = key[:-1] + 'c'

        # Convert pressure inches to hPa
        if key in ['baromrelin', 'baromabsin']:
            pressureHpa = float(value) * 33.6585
            value = "{:.2f}".format(pressureHpa)
            key = key[:-2] + 'hpa'

        # Convert speed mph to km/h
        if key in ['windspeedmph', 'windgustmph', 'maxdailygust']:
            speed = float(value) * 1.60934
            value = "{:.2f}".format(speed)
            if key == 'maxdailygust':
                key = key + 'kmh'
            else:
                key = key[:-3] + 'kmh'

        # Convert rain inches to mm
        if key in ['rainratein', 'eventrainin', 'hourlyrainin', 'dailyrainin', 'weeklyrainin', 'monthlyrainin', 'yearlyrainin', 'totalrainin']:
            mm = float(value) * 25.4
            value = "{:.1f}".format(mm)
            key = key[:-2] + 'mm'

        if fields:
            fields += "," + key + "=" + value
        else:
            fields = key + "=" + value

if __name__ == "__main__":
    # Add prometheus wsgi middleware to route /metrics requests
    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
        '/metrics': make_wsgi_app()
    })
    app.run(host="0.0.0.0", port=8088, debug=True)