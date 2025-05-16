from conversions import mph2kmh, mph2ms, mph2kts, mph2fps, in2mm, km2mi, inhg2hpa, inhg2mmhg, wm22lux, wm22fc, f2c, f2k, aqi_epa, aqi_mep, aqi_nepm, aqi_uk
import os
import logging
from flask import Flask, request
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import make_wsgi_app, Gauge, Info

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
prefix = os.environ.get('PREFIX', 'ecowitt_')

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
print ('  PREFIX:           ' + prefix)

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
        if key in ['PASSKEY', 'dateutc', 'runtime']:
            continue
        
        # Add these fields as INFO
        if key in ['stationtype', 'freq', 'model']:
            metrics[key].info({key: value})

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
                value = wm22lux(value)
            elif irradiance_unit == 'fc':
                value = wm22fc(value)
            metrics[key].set(value)

        # Temperature, default Fahrenheit
        # 'tempinf', 'tempf', 'temp1f', 'temp2f', 'temp3f', 'temp4f', 'temp5f', 'temp6f', 'temp7f', 'temp8f'
        if key.startswith('temp'):
            # Strip trailing f
            key = key[:-1]

            if temperature_unit == 'c':
                value = f2c(value)
            if temperature_unit == 'k':
                value = f2k(value)
            
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
                value = inhg2hpa(value)
            if pressure_unit == 'mmhg':
                value = inhg2mmhg(value)
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
                value = inhg2hpa(value)
            if pressure_unit == 'mmhg':
                value = inhg2mmhg(value)

            metrics['vpd'].set(value)

        # Wind speed, default mph
        if key in ['windspeedmph', 'windgustmph', 'maxdailygust']:
            if wind_unit == 'kmh':
                value = mph2kmh(value)
            elif wind_unit == 'ms':
                value = mph2ms(value)
            elif wind_unit == 'knots':
                value = mph2kts(value)
            elif wind_unit == 'fps':
                value = mph2fps(value)
            if key != 'maxdailygust':
                key = key[:-3]
            metrics['wind'].labels(key).set(value)
        
        # Support for WS90 with a haptic rain sensor
        # pylint: disable=consider-iterating-dictionary
        if key in rainmaps.keys():
            if rain_unit == 'mm':
                value = in2mm(value)
            mkey = rainmaps[key]
            metrics[mkey].set(value)

        # Rainfall, default inches
        if 'rain' in key:
        # 'rainratein', 'eventrainin', 'hourlyrainin', 'dailyrainin', 'weeklyrainin', 'monthlyrainin', 'yearlyrainin', 'totalrainin'
            if rain_unit == 'mm':
                value = in2mm(value)
            key = key[:-2]
            key = key.replace('rain', '')
            metrics['rain'].labels(key).set(value)

        # Lightning distance, default kilometers
        if key in ['lightning']:
            if distance_unit == 'km':
                metrics[key].set(value)
            elif distance_unit == 'mi':
                value = km2mi(value)
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
    metrics['stationtype'] = Info(name=prefix+'stationtype', documentation='Ecowitt station type')
    metrics['freq'] = Info(name=prefix+'freq', documentation='Ecowitt radio frequency')
    metrics['model'] = Info(name=prefix+'model', documentation='Ecowitt model')
    metrics['temp'] = Gauge(name=prefix+'temp', documentation='Temperature', unit=temperature_unit, labelnames=['sensor'])
    metrics['humidity'] = Gauge(name=prefix+'humidity', documentation='Relative humidity', unit='percent', labelnames=['sensor'])
    metrics['winddir'] = Gauge(name=prefix+'winddir', documentation='Wind direction', unit='degree')
    metrics['uv'] = Gauge(name=prefix+'uv', documentation='UV index')
    metrics['pm25'] = Gauge(name=prefix+'pm25', documentation='PM2.5 concentration', labelnames=['sensor'])
    metrics['aqi'] = Gauge(name=prefix+'aqi', documentation='Air quality index')
    metrics['batterystatus'] = Gauge(name=prefix+'batterystatus', documentation='Battery status', labelnames=['sensor'])
    metrics['batterylevel'] = Gauge(name=prefix+'batterylevel', documentation='Battery level', labelnames=['sensor'])
    metrics['solarradiation'] = Gauge(name=prefix+'solarradiation', documentation='Solar irradiance', unit='wm2')
    metrics['barom'] = Gauge(name=prefix+'barom', documentation='Barometer', unit=pressure_unit, labelnames=['sensor'])
    metrics['vpd'] = Gauge(name=prefix+'vpd', documentation='Vapour pressure deficit', unit=pressure_unit)
    metrics['wind'] = Gauge(name=prefix+'windspeed', documentation='Wind speed', unit=wind_unit, labelnames=['sensor'])
    metrics['rain'] = Gauge(name=prefix+'rain', documentation='Rainfall', unit=rain_unit, labelnames=['sensor'])
    metrics['lightning'] = Gauge(name=prefix+'lightning', documentation='Lightning distance', unit=distance_unit)
    metrics['lightning_num'] = Gauge(name=prefix+'lightning_num', documentation='Lightning daily count')
    metrics['ws90'] = Gauge(name=prefix+'wh90', documentation='WS90 electrical energy stored', unit='volt', labelnames=['sensor'])

    # Increase Flask logging if in debug mode
    if debug:
        app.logger.setLevel(logging.DEBUG)

    # Add prometheus wsgi middleware to route /metrics requests
    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
        '/metrics': make_wsgi_app()
    })
    app.run(host="0.0.0.0", port=8088, debug=debug)
