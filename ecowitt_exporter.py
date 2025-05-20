import os
import logging
import re
from flask import Flask, request
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import make_wsgi_app, Gauge, Info
from conversions import mph2kmh, mph2ms, mph2kts, mph2fps, in2mm, km2mi, inhg2hpa, inhg2mmhg, wm22lux, wm22fc, f2c, f2k, aqi_epa, aqi_mep, aqi_nepm, aqi_uk

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

def addmetric(metric: str, label: str, value: str):
    '''
    Set a metric in the Prometheus exporter 
    and optionally log a debug message.
    '''
    if debug:
        app.logger.debug("Set Prometheus metric %s: %s", metric, value)
    return metrics[metric].labels(label).set(value)

def calculate_aqi(standard: str, value: str) -> str:
    '''
    Calculate AQI (air quality index) using various
    different national standards.
    '''
    match standard:
        case 'uk':
            aqi = aqi_uk(value)
        case 'epa':
            aqi = aqi_epa(value)
        case 'mep':
            aqi = aqi_mep(value)
        case 'nepm':
            aqi = aqi_nepm(value)
    return aqi

@app.route('/report', methods=['POST'])
def logecowitt():

    # Retrieve the POST body
    data = request.form

    for key in data:
        # Process each key from the raw data, do unit conversions if necessary,
        # then add the results to the Prometheus exporter
        value = data[key]
        app.logger.debug("Received raw value %s: %s", key, value)

        # Ignore these fields
        if key in ['PASSKEY', 'dateutc', 'runtime']:
            continue
        
        # Add these fields as INFO
        elif key in ['stationtype', 'freq', 'model']:
            metrics[key].info({key: value})

        # No conversions needed
        elif key in ['winddir', 'uv', 'lightning_num']:
            addmetric(metric=key, value=value)
        
        # Support for WS90 capacitor
        elif key in ['ws90cap_volt', 'ws90batt']:
            addmetric(metric='ws90', label=key, value=value)

        # Battery status & levels
        elif 'batt' in key:
            # Battery level - returns battery level from 0-5
            if key in ['wh57batt', 'pm25batt1', 'pm25batt2']:
                addmetric(metric='batterylevel', label=key, value=value)
            # Battery status - returns 0 for OK and 1 for low
            else:
                addmetric(metric='batterystatus', label=key, value=value)

        # PM25
        # 'pm25_ch1', 'pm25_avg_24h_ch1'
        elif key.startswith('pm25'):
            # Check for invalid readings from the WH41 PM2.5 sensor when the battery is low
            # https://github.com/djjudas21/ecowitt-exporter/issues/17
            # If we find bad data, just skip the entire PM2.5 section
            if (data.get('pm25batt1') == '1' and data.get('pm25_ch1') == '1000') or (data.get('pm25batt2') == '1' and data.get('pm25_ch2') == '1000'):
                app.logger.debug(f"Drop erroneous PM25 reading {key}: {value}")
                continue

            # Drop PM25 prefix
            key = key.replace('pm25_', '')

            # Get & drop sensor ch suffix
            sensorsearch = re.search(r"(ch\d)$", key)
            sensor = sensorsearch.group(1)
            key = re.sub(r"ch\d$", '', key)

            # Generate series label
            if key.startswith('avg_24h'):
                series = 'avg_24h'
            else:
                series = 'realtime'

            # Log the PM25 metric
            addmetric(metric='pm25', label=(series, sensor), value=value)

            # Calculate AQI from PM25
            if key.startswith('avg_24h'):
                aqi = calculate_aqi(standard=aqi_standard, value=value)
                addmetric(metric='aqi', label=aqi_standard, value=value)

        # Humidity - no conversion needed
        elif key.startswith('humidity'):
            match key:
                case 'humidity':
                    label = 'outdoor'
                case 'humidityin':
                    label = 'indoor'
                case _:
                    label = f'ch{key[-1]}'
            # pylint: disable=used-before-assignment
            addmetric(metric='humidity', label=label, value=value)

        # Solar irradiance, default W/m^2
        elif key in ['solarradiation']:
            if irradiance_unit == 'lx':
                value = wm22lux(value)
            elif irradiance_unit == 'fc':
                value = wm22fc(value)
            addmetric(metric='solarradiation', value=value)

        # Temperature, default Fahrenheit
        # 'tempinf', 'tempf', 'temp1f', 'temp2f', 'temp3f', 'temp4f', 'temp5f', 'temp6f', 'temp7f', 'temp8f'
        elif key.startswith('temp'):
            # Strip trailing f
            key = key[:-1]

            if temperature_unit == 'c':
                value = f2c(value)
            elif temperature_unit == 'k':
                value = f2k(value)
            
            if key == 'tempin':
                label = 'indoor'
            elif key == 'temp':
                label = 'outdoor'
            else:
                label = f'ch{key[-1]}'

            addmetric(metric='temp', label=label, value=value)

        # Pressure, default inches Hg
        elif key.startswith('barom'):
            if pressure_unit == 'hpa':
                value = inhg2hpa(value)
            elif pressure_unit == 'mmhg':
                value = inhg2mmhg(value)
            # Remove 'in' suffix
            key = key[:-2]

            if key == 'baromrel':
                label = 'relative'
            elif key == 'abs':
                label = 'absolute'
            addmetric(metric='barom', label=label, value=value)

        # VPD, default inches Hg
        elif key in ['vpd']:
            if pressure_unit == 'hpa':
                value = inhg2hpa(value)
            elif pressure_unit == 'mmhg':
                value = inhg2mmhg(value)

            addmetric(metric='vpd', value=value)

        # Wind speed, default mph
        elif key in ['windspeedmph', 'windgustmph', 'maxdailygust']:
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
            addmetric(metric='wind', label=key, value=value)
        
        # Support for WS90 with a haptic rain sensor
        elif key.endswith('piezo'):
            if rain_unit == 'mm':
                value = in2mm(value)
            mkey = rainmaps[key]
            addmetric(metric='rain', label=kkey, value=value)

        # Rainfall, default inches
        elif 'rain' in key:
        # 'rainratein', 'eventrainin', 'hourlyrainin', 'dailyrainin', 'weeklyrainin', 'monthlyrainin', 'yearlyrainin', 'totalrainin'
            if rain_unit == 'mm':
                value = in2mm(value)
            key = key[:-2]
            key = key.replace('rain', '')
            addmetric(metric='rain', label=key, value=value)

        # Lightning distance, default kilometers
        elif key in ['lightning']:
            if distance_unit == 'km':
                addmetric(metric='lightning', value=value)
            elif distance_unit == 'mi':
                value = km2mi(value)
                addmetric(metric='lightning', value=value)


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
    metrics['pm25'] = Gauge(name=prefix+'pm25', documentation='PM2.5 concentration', labelnames=['series', 'sensor'])
    metrics['aqi'] = Gauge(name=prefix+'aqi', documentation='Air quality index', labelnames=['standard'])
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
