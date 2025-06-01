import aqi

def mph2kmh(mph: str) -> str:
    '''Convert mph to km/h'''
    kmh = float(mph) * 1.60934
    return "{:.2f}".format(kmh)

def mph2ms(mph: str) -> str:
    '''Convert mph to m/s'''
    speedms = float(mph) / 2.237
    return "{:.2f}".format(speedms)

def mph2kts(mph: str) -> str:
    '''Convert mph to knots'''
    knots = float(mph) / 1.151
    return "{:.2f}".format(knots)

def mph2fps(mph: str) -> str:
    '''Convert mph to fps'''
    fps = float(mph) * 1.467
    return "{:.2f}".format(fps)

def in2mm(inches: str) -> str:
    '''Convert inches to mm'''
    mm = float(inches) * 25.4
    return "{:.1f}".format(mm)

def km2mi(km: str) -> str:
    '''Convert km to miles'''
    distancemi = float(km) / 1.60934
    return "{:.2f}".format(distancemi)

def inhg2hpa(inhg: str) -> str:
    '''Convert inches Hg to hPa'''
    pressurehpa = float(inhg) * 33.8639
    return "{:.2f}".format(pressurehpa)

def inhg2mmhg(inhg: str) -> str:
    '''Convert inches Hg to mmHg'''
    pressuremmhg = float(inhg) * 25.4
    return "{:.2f}".format(pressuremmhg)

def wm22lux(wm2: str) -> str:
    '''Convert degrees W/m2 to lux'''
    irradiance_lx = float(wm2) / 0.0079
    return "{:.2f}".format(irradiance_lx)

def wm22fc(wm2: str) -> str:
    '''Convert degrees W/m2 to foot candle'''
    irradiance_lx = float(wm2) * 6.345
    return "{:.2f}".format(irradiance_lx)

def f2c(f: str) -> str:
    '''Convert degrees Fahrenheit to Celsius'''
    tempc = (float(f) - 32) * 5/9
    return "{:.2f}".format(tempc)

def f2k(f: str) -> str:
    '''Convert degrees Fahrenheit to Kelvin'''
    tempk = (float(f) - 32) * 5/9 + 273.15
    return "{:.2f}".format(tempk)

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

def mph2beaufort(speed: str):
    '''
    Calculate the Beaufort scale number from the windspeed in mph
    '''
    speed = float(speed)
    if speed <= 1:
        beaufort = 0
    elif 1 < speed <= 3:
        beaufort = 1
    elif 3 < speed <= 7:
        beaufort = 2
    elif 7 < speed <= 12:
        beaufort = 3
    elif 12 < speed <= 18:
        beaufort = 4
    elif 18 < speed <= 24:
        beaufort = 5
    elif 24 < speed <= 31:
        beaufort = 6
    elif 31 < speed <= 38:
        beaufort = 7
    elif 38 < speed <= 46:
        beaufort = 8
    elif 46 < speed <= 54:
        beaufort = 9
    elif 54 < speed <= 63:
        beaufort = 10
    elif 63 < speed <= 73:
        beaufort = 11
    elif speed >= 73:
        beaufort = 12
    else:
        beaufort = None
    return beaufort