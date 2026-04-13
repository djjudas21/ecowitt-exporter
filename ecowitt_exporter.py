import os
import logging
import re
import time
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

# Comma-separated list of sensor names to pre-seed in
# ecowitt_sensor_last_report_timestamp_seconds at startup. Without this, the
# per-sensor freshness metric is only created when a sensor first pushes data,
# which means staleness alerts of the form
# `time() - ecowitt_sensor_last_report_timestamp_seconds{sensor="soilmoisture1"} > N`
# return no data (and therefore never fire) if the exporter restarts while
# the sensor is already offline. Seeding with the current time gives the alert
# a grace period equal to its `for:` duration.
sensors_to_track = [
    s.strip() for s in os.environ.get('SENSORS_TO_TRACK', '').split(',') if s.strip()
]

co2_location = os.environ.get('CO2_LOCATION')
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
print ('  SENSORS_TO_TRACK: ' + (','.join(sensors_to_track) if sensors_to_track else '(none)'))

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
                # Per-sensor last-seen timestamp for PM2.5 sensors (see note
                # on sensor freshness tracking at bottom of /report handler).
                # The WH41 PM2.5 sensor can drop off the radio and we want to
                # alert on that independently of the gateway.
                if key.startswith('pm25batt'):
                    addmetric(metric='sensor_last_report_timestamp',
                              label=[key], value=time.time())
            # Battery voltage - returns a decimal voltage e.g. 1.7
            elif key.startswith('soil') or key.startswith('ws90'):
                addmetric(metric='batteryvoltage', label=[key, 'volt'], value=value)
                # Per-sensor last-seen timestamp (see note on sensor freshness
                # tracking at bottom of /report handler).
                if key.startswith('soilbatt'):
                    addmetric(metric='sensor_last_report_timestamp',
                              label=[key], value=time.time())
            # Battery status - returns 0 for OK and 1 for low
            else:
                addmetric(metric='batterystatus', label=[key], value=value)

        # Soil moisture
        elif key.startswith('soilmoisture'):
            addmetric(metric='soilmoisture', label=[key, 'percent'], value=value)
            # Per-sensor last-seen timestamp (see note on sensor freshness
            # tracking at bottom of /report handler).
            addmetric(metric='sensor_last_report_timestamp',
                      label=[key], value=time.time())

        # WH45 CO2/AQI multi-sensor (tf_co2, humi_co2, pm25_co2,
        # pm25_24h_co2, pm10_co2, pm10_24h_co2, co2, co2_24h)
        # Must be checked BEFORE the generic pm25 handler.
        elif key == 'tf_co2':
            if temperature_unit == 'c':
                value = f2c(value)
            elif temperature_unit == 'k':
                value = f2k(value)
            location = co2_location if co2_location else 'co2'
            addmetric(metric='temp', label=['co2', temperature_unit, location], value=value)
            addmetric(metric='sensor_last_report_timestamp',
                      label=['co2'], value=time.time())

        elif key == 'humi_co2':
            location = co2_location if co2_location else 'co2'
            addmetric(metric='humidity', label=['co2', 'percent', location], value=value)

        elif key == 'pm25_co2':
            addmetric(metric='pm25', label=['realtime', 'co2', 'μgm3'], value=value)

        elif key == 'pm25_24h_co2':
            addmetric(metric='pm25', label=['avg_24h', 'co2', 'μgm3'], value=value)
            aqi = calculate_aqi(standard=aqi_standard, value=value)
            addmetric(metric='aqi', label=[aqi_standard, 'co2'], value=aqi)

        elif key == 'pm10_co2':
            addmetric(metric='pm10', label=['realtime', 'co2', 'μgm3'], value=value)

        elif key == 'pm10_24h_co2':
            addmetric(metric='pm10', label=['avg_24h', 'co2', 'μgm3'], value=value)

        elif key == 'co2':
            addmetric(metric='co2', label=['realtime', 'ppm'], value=value)

        elif key == 'co2_24h':
            addmetric(metric='co2', label=['avg_24h', 'ppm'], value=value)

        # PM25 (WH41 channel sensors)
        # 'pm25_ch1', 'pm25_avg_24h_ch1'
        elif key.startswith('pm25'):
            # Check for invalid readings from the WH41 PM2.5 sensor when the battery is low
            # https://github.com/djjudas21/ecowitt-exporter/issues/17
            # If we find bad data, just skip the entire PM2.5 section
            if (data.get('pm25batt1') == '1' and data.get('pm25_ch1') == '1000') or (data.get('pm25batt2') == '1' and data.get('pm25_ch2') == '1000'):
                app.logger.debug(f"Drop erroneous PM25 reading {key}: {value}")
                continue

            # Preserve the original key (e.g. 'pm25_ch1') so we can use it as
            # a per-sensor last-seen label below.
            original_key = key

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

            # Per-sensor last-seen timestamp for PM2.5 sensors (see note on
            # sensor freshness tracking at bottom of /report handler). Only
            # update on the realtime series; avg_24h is a derived rollup and
            # doesn't represent a fresh sensor push.
            if series == 'realtime':
                addmetric(metric='sensor_last_report_timestamp',
                          label=[original_key], value=time.time())

            # Calculate AQI from PM25
            if key.startswith('avg_24h'):
                aqi = calculate_aqi(standard=aqi_standard, value=value)
                addmetric(metric='aqi', label=[aqi_standard, sensor], value=aqi)

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


    # Record the wall-clock time of this successful push from the gateway.
    # Prometheus can then use `time() - ecowitt_last_report_timestamp_seconds`
    # to detect a stale gateway (gauges persist their last value forever,
    # so absent_over_time() on data metrics never fires if the gateway dies).
    #
    # Per-sensor timestamps are updated inline above as each sensor's key is
    # processed, so individual sensor staleness can also be detected even when
    # the gateway is otherwise healthy (e.g. a single soil probe goes offline
    # or out of radio range).
    metrics['last_report_timestamp'].set(time.time())

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
    metrics['aqi'] = Gauge(name='ecowitt_aqi', documentation='Air quality index', labelnames=['standard', 'sensor'])
    metrics['pm10'] = Gauge(name='ecowitt_pm10', documentation='PM10 concentration', labelnames=['series', 'sensor', 'unit'])
    metrics['co2'] = Gauge(name='ecowitt_co2', documentation='CO2 concentration', labelnames=['series', 'unit'])
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
    metrics['last_report_timestamp'] = Gauge(
        name='ecowitt_last_report_timestamp_seconds',
        documentation='Unix timestamp of the most recent successful POST from the Ecowitt gateway to /report. Use `time() - ecowitt_last_report_timestamp_seconds > N` to detect a stale or offline gateway.'
    )
    # Seed with current time so the freshness alert does not fire immediately
    # after an exporter restart (it gets a grace period equal to the alert
    # `for:` duration before a real gateway push updates the value).
    metrics['last_report_timestamp'].set(time.time())

    # Per-sensor last-seen timestamp. Updated whenever a specific sensor's
    # data appears in a push, so individual sensors can be monitored for
    # staleness even if the gateway itself is healthy. Used for soilmoisture*,
    # soilbatt*, pm25_ch* and pm25batt* in particular - both soil probes
    # losing radio sync (plants going unwatered) and WH41 PM2.5 sensors going
    # offline are real failure modes we want to alert on.
    metrics['sensor_last_report_timestamp'] = Gauge(
        name='ecowitt_sensor_last_report_timestamp_seconds',
        documentation='Unix timestamp of the most recent report from a specific sensor. Use `time() - ecowitt_sensor_last_report_timestamp_seconds{sensor="soilmoisture1"} > N` to detect a stale individual sensor.',
        labelnames=['sensor']
    )

    # Pre-seed per-sensor freshness timestamps for every sensor named in
    # SENSORS_TO_TRACK. This ensures the metric exists for each expected
    # sensor immediately at exporter startup, so staleness alerts like
    # `time() - ecowitt_sensor_last_report_timestamp_seconds{sensor="soilmoisture1"} > 600`
    # return a value (and can fire) even if the exporter restarted while the
    # sensor was offline. Without seeding, the metric wouldn't exist until
    # the sensor's first push, so `time() - <missing>` returns no data and
    # the alert silently never fires. Seeding with `time.time()` gives a
    # grace period equal to the alert's `for:` duration before it trips.
    for sensor_name in sensors_to_track:
        metrics['sensor_last_report_timestamp'].labels(sensor=sensor_name).set(time.time())

    # Increase Flask logging if in debug mode
    if debug:
        app.logger.setLevel(logging.DEBUG)

    # Add prometheus wsgi middleware to route /metrics requests
    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
        '/metrics': make_wsgi_app()
    })
    app.run(host="0.0.0.0", port=8088, debug=debug)
