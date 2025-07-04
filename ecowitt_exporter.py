import os
import logging
import re
from flask import Flask, request
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import make_wsgi_app, Gauge, Info
from conversions import mph2kmh, mph2ms, mph2kts, mph2fps, in2mm, km2mi, inhg2hpa, inhg2mmhg, wm22lux, wm22fc, f2c, f2k, aqi_epa, aqi_mep, aqi_nepm, aqi_uk, mph2beaufort

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

outdoor_location = os.environ.get('OUTDOOR_LOCATION')
indoor_location = os.environ.get('INDOOR_LOCATION')
temp1_location = os.environ.get('TEMP1_LOCATION')
temp2_location = os.environ.get('TEMP2_LOCATION')
temp3_location = os.environ.get('TEMP3_LOCATION')
temp4_location = os.environ.get('TEMP4_LOCATION')
temp5_location = os.environ.get('TEMP5_LOCATION')
temp6_location = os.environ.get('TEMP6_LOCATION')
temp7_location = os.environ.get('TEMP7_LOCATION')
temp8_location = os.environ.get('TEMP8_LOCATION')

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

# pylint: disable=dangerous-default-value
def addmetric(metric: str, value: str, label: list = []):
    '''
    Set a metric in the Prometheus exporter 
    and optionally log a debug message.
    '''
    if debug:
        app.logger.debug("Set Prometheus metric %s: %s", metric, value)
    if label:
        status = metrics[metric].labels(*label).set(value)
    else:
        status = metrics[metric].set(value)
    return status

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
        elif key in ['winddir', 'uv', 'lightning_num', 'lightning_time']:
            addmetric(metric=key, value=value)
        
        # Support for WS90 capacitor
        elif key in ['ws90cap_volt']:
            addmetric(metric='ws90', label=[key, 'volt'], value=value)

        # Battery status & levels
        elif 'batt' in key:
            # Battery level - returns battery level from 0-5
            if key in ['wh57batt', 'pm25batt1', 'pm25batt2']:
                addmetric(metric='batterylevel', label=[key], value=value)
            # Battery voltage - returns a decimal voltage e.g. 1.7
            elif key.startswith('soil') or key.startswith('ws90'):
                addmetric(metric='batteryvoltage', label=[key, 'volt'], value=value)
            # Battery status - returns 0 for OK and 1 for low
            else:
                addmetric(metric='batterystatus', label=[key], value=value)

        # Soil moisture
        elif key.startswith('soilmoisture'):
            addmetric(metric='soilmoisture', label=[key, 'percent'], value=value)

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
            addmetric(metric='pm25', label=[series, sensor, 'μgm3'], value=value)

            # Calculate AQI from PM25
            if key.startswith('avg_24h'):
                aqi = calculate_aqi(standard=aqi_standard, value=value)
                addmetric(metric='aqi', label=[aqi_standard], value=aqi)

        # Humidity - no conversion needed
        elif key.startswith('humidity'):
            match key:
                case 'humidity':
                    label = 'outdoor'
                    location = outdoor_location if outdoor_location else label
                case 'humidityin':
                    label = 'indoor'
                    location = indoor_location if indoor_location else label
                case _:
                    label = f'ch{key[-1]}'
                    location = globals()[f'temp{key[-1]}_location']
            # pylint: disable=used-before-assignment
            addmetric(metric='humidity', label=[label, 'percent', location], value=value)

        # Solar irradiance, default W/m^2
        elif key in ['solarradiation']:
            if irradiance_unit == 'lx':
                value = wm22lux(value)
            elif irradiance_unit == 'fc':
                value = wm22fc(value)
            addmetric(metric='solarradiation', label=[irradiance_unit], value=value)

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
                location = indoor_location if indoor_location else label
            elif key == 'temp':
                label = 'outdoor'
                location = outdoor_location if outdoor_location else label
            else:
                label = f'ch{key[-1]}'
                location = globals()[f'temp{key[-1]}_location']

            addmetric(metric='temp', label=[label, temperature_unit, location], value=value)

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
            elif key == 'baromabs':
                label = 'absolute'
            addmetric(metric='barom', label=[label, pressure_unit], value=value)

        # VPD, default inches Hg
        elif key in ['vpd']:
            if pressure_unit == 'hpa':
                value = inhg2hpa(value)
            elif pressure_unit == 'mmhg':
                value = inhg2mmhg(value)

            addmetric(metric='vpd', label=[pressure_unit], value=value)

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

            if key == 'windspeedmph':
                beaufort = mph2beaufort(value)
                addmetric(metric='wind_beaufort', value=beaufort)

            if key != 'maxdailygust':
                key = key[:-3]
            addmetric(metric='wind', label=[key, wind_unit], value=value)
        
        # Support for WS90 with a haptic rain sensor
        elif key.endswith('piezo'):
            if rain_unit == 'mm':
                value = in2mm(value)
            mkey = rainmaps[key]
            addmetric(metric='rain', label=[key, rain_unit], value=value)

        # Rainfall, default inches
        elif 'rain' in key:
        # 'rainratein', 'eventrainin', 'hourlyrainin', 'dailyrainin', 'weeklyrainin', 'monthlyrainin', 'yearlyrainin', 'totalrainin'
            if rain_unit == 'mm':
                value = in2mm(value)
            key = key[:-2]
            key = key.replace('rain', '')
            addmetric(metric='rain', label=[key, rain_unit], value=value)

        # Lightning distance, default kilometers
        elif key in ['lightning']:
            if distance_unit == 'km':
                addmetric(metric='lightning', label=[distance_unit], value=value)
            elif distance_unit == 'mi':
                value = km2mi(value)
                addmetric(metric='lightning', label=[distance_unit], value=value)


    # Return a 200 to the weather station
    response = app.response_class(
            response='OK',
            status=200,
            mimetype='application/json'
    )
    return response

if __name__ == "__main__":

    # Set up various Prometheus metrics with descriptions and units
    metrics['stationtype'] = Info(name='ecowitt_stationtype', documentation='Ecowitt station type')
    metrics['freq'] = Info(name='ecowitt_freq', documentation='Ecowitt radio frequency')
    metrics['model'] = Info(name='ecowitt_model', documentation='Ecowitt model')
    metrics['temp'] = Gauge(name='ecowitt_temp', documentation='Temperature', labelnames=['sensor', 'unit', 'location'])
    metrics['humidity'] = Gauge(name='ecowitt_humidity', documentation='Relative humidity', labelnames=['sensor', 'unit', 'location'])
    metrics['winddir'] = Gauge(name='ecowitt_winddir', documentation='Wind direction')
    metrics['uv'] = Gauge(name='ecowitt_uv', documentation='UV index')
    metrics['pm25'] = Gauge(name='ecowitt_pm25', documentation='PM2.5 concentration', labelnames=['series', 'sensor', 'unit'])
    metrics['aqi'] = Gauge(name='ecowitt_aqi', documentation='Air quality index', labelnames=['standard'])
    metrics['batterystatus'] = Gauge(name='ecowitt_batterystatus', documentation='Battery status', labelnames=['sensor'])
    metrics['batterylevel'] = Gauge(name='ecowitt_batterylevel', documentation='Battery level', labelnames=['sensor'])
    metrics['batteryvoltage'] = Gauge(name='ecowitt_batteryvoltage', documentation='Battery voltage', labelnames=['sensor', 'unit'])
    metrics['solarradiation'] = Gauge(name='ecowitt_solarradiation', documentation='Solar irradiance', labelnames=['unit'])
    metrics['barom'] = Gauge(name='ecowitt_barom', documentation='Barometer', labelnames=['sensor', 'unit'])
    metrics['vpd'] = Gauge(name='ecowitt_vpd', documentation='Vapour pressure deficit', labelnames=['unit'])
    metrics['wind'] = Gauge(name='ecowitt_windspeed', documentation='Wind speed', labelnames=['sensor', 'unit'])
    metrics['wind_beaufort'] = Gauge(name='ecowitt_windspeed_beaufort', documentation='Wind Beaufort scale')
    metrics['rain'] = Gauge(name='ecowitt_rain', documentation='Rainfall', labelnames=['sensor', 'unit'])
    metrics['lightning'] = Gauge(name='ecowitt_lightning', documentation='Lightning distance', labelnames=['unit'])
    metrics['lightning_num'] = Gauge(name='ecowitt_lightning_num', documentation='Lightning daily count')
    metrics['lightning_time'] = Gauge(name='ecowitt_lightning_time', documentation='Lightning last strike')
    metrics['ws90'] = Gauge(name='ecowitt_wh90', documentation='WS90 electrical energy stored', labelnames=['sensor', 'unit'])
    metrics['soilmoisture'] = Gauge(name='ecowitt_soilmoisture', documentation='Soil moisture', labelnames=['sensor', 'unit'])

    # Increase Flask logging if in debug mode
    if debug:
        app.logger.setLevel(logging.DEBUG)

    # Add prometheus wsgi middleware to route /metrics requests
    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
        '/metrics': make_wsgi_app()
    })
    app.run(host="0.0.0.0", port=8088, debug=debug)
