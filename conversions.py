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