import os
import logging
import aqi
from flask import Flask, request
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import make_wsgi_app, Gauge

app = Flask(__name__)

debug = os.environ.get('DEBUG', 'no') == 'yes'
temperature_unit = os.environ.get('TEMPERATURE_UNIT', 'c')
pressure_unit = os.environ.get('PRESSURE_UNIT', 'hpa')
wind_unit = os.environ.get('WIND_UNIT', 'kmh')
rain_unit = os.environ.get('RAIN_UNIT', 'mm')
distance_unit = os.environ.get('DISTANCE_UNIT', 'km')
irradiance_unit = os.environ.get('IRRADIANCE_UNIT', 'wm2')
aqi_standard = os.environ.get('AQI_STANDARD', 'uk')
station_id = os.environ.get('STATION_ID', 'ecowitt')

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
print ('  AQI STANDARD:     ' + aqi_standard)
print ('  STATION_ID:       ' + station_id)

# Declare metrics as a global
metrics={}

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
    
def aqi_uk(concentration):
    '''
    Calculate the AQI using the UK DAQI standard
    https://en.wikipedia.org/wiki/Air_quality_index#United_Kingdom
    '''
    concentration = float(concentration)
    if concentration < 12:
        index = 1
    elif 12 <= concentration < 24:
        index = 2
    elif 24 <= concentration < 36:
        index = 3
    elif 36 <= concentration < 42:
        index = 4
    elif 42 <= concentration < 48:
        index = 5
    elif 48 <= concentration < 54:
        index = 6
    elif 54 <= concentration < 59:
        index = 7
    elif 59 <= concentration < 65:
        index = 8
    elif 65 <= concentration < 71:
        index = 9
    elif concentration >= 71:
        index = 10
    else:
        index = None
    return index

def aqi_nepm(concentration):
    '''
    Calculate the AQI using the Austration NEPM standard
    '''
    concentration = float(concentration)
    index = int(round(100 * concentration / 25))
    return index

def aqi_epa(concentration):
    '''
    Calculate the AQI using the US EPA standard
    '''
    index = aqi.to_iaqi(aqi.POLLUTANT_PM25, concentration, algo=aqi.ALGO_EPA)
    return index

def aqi_mep(concentration):
    '''
    Calculate the AQI using the China MEP standard
    '''
    index = aqi.to_iaqi(aqi.POLLUTANT_PM25, concentration, algo=aqi.ALGO_MEP)
    return index

# Support for WS90 with a haptic rain sensor
rainmaps = {
        "rrain_piezo": "rainrate",
        "erain_piezo": "eventrain",
        "hrain_piezo": "hourlyrain",
        "drain_piezo": "dailyrain",
        "wrain_piezo": "weeklyrain",
        "mrain_piezo": "monthlyrain",
        "yrain_piezo": "yearlyrain"
}


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
        if key in ['PASSKEY', 'stationtype', 'dateutc', 'freq', 'model', 'runtime']:
            continue

        # No conversions needed
        if key in ['winddir', 'uv', 'lightning_num']:
            metrics[key].set(value)
        
        # Support for WS90 capacitor
        if key in ['ws90cap_volt', 'ws90batt']:
            metrics['ws90'].labels(key).set(value)

        # Battery status & levels
        if 'batt' in key:
            # Battery level - returns battery level from 0-5
            if key in ['wh57batt', 'pm25batt1', 'pm25batt2']:
                metrics['batterylevel'].labels(key).set(value)
            # Battery status - returns 0 for OK and 1 for low
            else:
                metrics['batterystatus'].labels(key).set(value)

        # PM25
        # 'pm25_ch1', 'pm25_avg_24h_ch1'
        if key.startswith('pm25'):
            key = key.replace('pm25_', '')
            metrics['pm25'].labels(key).set(value)

        # Humidity - no conversion needed
        if key.startswith('humidity'):
            if key == 'humidity':
                label = 'outdoor'
            elif key == 'humidityin':
                label = 'indoor'
            metrics['humidity'].labels(label).set(value)

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
            metrics[key].set(value)

        # Temperature, default Fahrenheit
        # 'tempinf', 'tempf', 'temp1f', 'temp2f', 'temp3f', 'temp4f', 'temp5f', 'temp6f', 'temp7f', 'temp8f'
        if key.startswith('temp'):
            # Strip trailing f
            key = key[:-1]

            if temperature_unit == 'c':
                # Convert degrees Fahrenheit to Celsius
                tempc = (float(value) - 32) * 5/9
                value = "{:.2f}".format(tempc)
            if temperature_unit == 'k':
                # Convert degrees Fahrenheit to Kelvin
                tempk = (float(value) - 32) * 5/9 + 273.15
                value = "{:.2f}".format(tempk)
            
            if key == 'tempin':
                label = 'indoor'
            elif key == 'temp':
                label = 'outdoor'
            else:
                label = f'ch{key[-1]}'

            metrics['temp'].labels(label).set(value)

        # Pressure, default inches Hg
        if key.startswith('barom'):
            if pressure_unit == 'hpa':
                # Convert inches Hg to hPa
                pressurehpa = float(value) * 33.8639
                value = "{:.2f}".format(pressurehpa)
            if pressure_unit == 'mmhg':
                # Convert inches Hg to mmHg
                pressuremmhg = float(value) * 25.4
                value = "{:.2f}".format(pressuremmhg)
            # Remove 'in' suffix
            key = key[:-2]

            if key == 'baromrel':
                label = 'relative'
            elif key == 'abs':
                label = 'absolute'
            metrics['barom'].labels(label).set(value)

        # VPD, default inches Hg
        if key in ['vpd']:
            if pressure_unit == 'hpa':
                # Convert inches Hg to hPa
                pressurehpa = float(value) * 33.8639
                value = "{:.2f}".format(pressurehpa)
            if pressure_unit == 'mmhg':
                # Convert inches Hg to mmHg
                pressuremmhg = float(value) * 25.4
                value = "{:.2f}".format(pressuremmhg)
            metrics['vpd'].set(value)

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
            metrics['wind'].labels(key).set(value)
        
        # Support for WS90 with a haptic rain sensor
        # pylint: disable=consider-iterating-dictionary
        if key in rainmaps.keys():
            if rain_unit == 'mm':
                # Convert inches to mm
                rainmm = float(value) * 25.4
                value = "{:.1f}".format(rainmm)
            mkey = rainmaps[key]
            metrics[mkey].set(value)

        # Rainfall, default inches
        if 'rain' in key:
        # 'rainratein', 'eventrainin', 'hourlyrainin', 'dailyrainin', 'weeklyrainin', 'monthlyrainin', 'yearlyrainin', 'totalrainin'
            if rain_unit == 'mm':
                # Convert inches to mm
                rainmm = float(value) * 25.4
                value = "{:.1f}".format(rainmm)
            key = key[:-2]
            key = key.replace('rain', '')
            metrics['rain'].labels(key).set(value)

        # Lightning distance, default kilometers
        if key in ['lightning']:
            if distance_unit == 'km':
                metrics[key].set(value)
            elif distance_unit == 'mi':
                # Convert km to miles
                distancemi = float(value) / 1.60934
                value = "{:.2f}".format(distancemi)
                metrics[key].set(value)

    # Add Air Quality Index (AQI)
    if data.get('pm25_avg_24h_ch1'):
        if aqi_standard == 'uk':
            results['aqi'] = aqi_uk(data['pm25_avg_24h_ch1'])
        elif aqi_standard == 'epa':
            results['aqi'] = aqi_epa(data['pm25_avg_24h_ch1'])
        elif aqi_standard == 'mep':
            results['aqi'] = aqi_mep(data['pm25_avg_24h_ch1'])
        elif aqi_standard == 'nepm':
            results['aqi'] = aqi_nepm(data['pm25_avg_24h_ch1'])

    if data.get('pm25_avg_24h_ch2'):
        if aqi_standard == 'uk':
            results['aqi'] = aqi_uk(data['pm25_avg_24h_ch2'])
        elif aqi_standard == 'epa':
            results['aqi'] = aqi_epa(data['pm25_avg_24h_ch2'])
        elif aqi_standard == 'mep':
            results['aqi'] = aqi_mep(data['pm25_avg_24h_ch2'])
        elif aqi_standard == 'nepm':
            results['aqi'] = aqi_nepm(data['pm25_avg_24h_ch2'])

    # Check data from the WH41 PM2.5 sensor
    # If the battery is low it gives junk readings
    # https://github.com/djjudas21/ecowitt-exporter/issues/17
    if data.get('pm25batt1') == '1' and data.get('pm25_ch1') == '1000':
        # Drop erroneous readings
        app.logger.debug("Drop erroneous PM25 reading 'pm25_ch1': %s", results['pm25_ch1'])
        del results['pm25_ch1']
        del results['pm25_avg_24h_ch1']
        del results['aqi']
    if data.get('pm25batt2') == '1' and data.get('pm25_ch2') == '1000':
        # Drop erroneous readings
        app.logger.debug("Drop erroneous PM25 reading 'pm25_ch2': %s", results['pm25_ch2'])
        del results['pm25_ch2']
        del results['pm25_avg_24h_ch2']
        del results['aqi']

    # Now loop on our processed results and do things with them
    points = []
    for key, value in results.items():
        # Send the data to the Prometheus exporter
        metrics[key].set(value)
        app.logger.debug("Set Prometheus metric %s: %s", key, value)

    # Return a 200 to the weather station
    response = app.response_class(
            response='OK',
            status=200,
            mimetype='application/json'
    )
    return response

if __name__ == "__main__":

    # Set up various Prometheus metrics with descriptions and units
    metrics['temp'] = Gauge(name='temp', documentation='Temperature', unit=temperature_unit, labelnames=['sensor'])
    metrics['humidity'] = Gauge(name='humidity', documentation='Relative humidity', unit='percent', labelnames=['sensor'])
    metrics['winddir'] = Gauge(name='winddir', documentation='Wind direction', unit='degree')
    metrics['uv'] = Gauge(name='uv', documentation='UV index')
    metrics['pm25'] = Gauge(name='pm25', documentation='PM2.5 concentration', labelnames=['sensor'])
    metrics['aqi'] = Gauge(name='aqi', documentation='Air quality index')
    metrics['batterystatus'] = Gauge(name='batterystatus', documentation='Battery status', labelnames=['sensor'])
    metrics['batterylevel'] = Gauge(name='batterylevel', documentation='Battery level', labelnames=['sensor'])
    metrics['solarradiation'] = Gauge(name='solarradiation', documentation='Solar irradiance', unit='wm2')
    metrics['barom'] = Gauge(name='barom', documentation='Barometer', unit=pressure_unit, labelnames=['sensor'])
    metrics['vpd'] = Gauge(name='vpd', documentation='Vapour pressure deficit', unit=pressure_unit)
    metrics['wind'] = Gauge(name='windspeed', documentation='Wind speed', unit=wind_unit, labelnames=['sensor'])
    metrics['rain'] = Gauge(name='rain', documentation='Rainfall', unit=rain_unit, labelnames=['sensor'])
    metrics['lightning'] = Gauge(name='lightning', documentation='Lightning distance', unit=distance_unit)
    metrics['lightning_num'] = Gauge(name='lightning_num', documentation='Lightning daily count')
    metrics['ws90'] = Gauge(name='wh90', documentation='WS90 electrical energy stored', unit='volt', labelnames=['sensor'])

    # Increase Flask logging if in debug mode
    if debug:
        app.logger.setLevel(logging.DEBUG)

    # Add prometheus wsgi middleware to route /metrics requests
    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
        '/metrics': make_wsgi_app()
    })
    app.run(host="0.0.0.0", port=8088, debug=debug)
