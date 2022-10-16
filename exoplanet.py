from locale import ALT_DIGITS
import requests
import lxml.html
import re
from collections import OrderedDict
import datetime
import csv

session = requests.session()


# 54.59769273166332, -2.0819179261299876

LONG = 360 - 2.0819179261299876 # 0..360
LAT = 54.59769273166332 # -90..90
NOW = datetime.date.today()
TODAY = NOW.isoformat()
MONTH = (NOW + datetime.timedelta(days=30)).isoformat()
DUSK_TIME = datetime.time(hour=19, minute=30)
END_CUTOFF_HOUR = 3
ALT_MIN = 30

CANNED = False
if CANNED:
    with open('exo.html', 'r') as f:
        lines = f.readlines()
else:
    url = f"http://var2.astro.cz/ETD/predictions.php?delka={LONG}&submit=submit&sirka={LAT}"
    response = session.post(url)
    response.raise_for_status()

    url = f"http://var2.astro.cz/ETD/predictions.php?init={TODAY}&till={MONTH}&submit=Show&f=userdefined"
    response = session.post(url)
    response.raise_for_status()

    with open('exo.html', 'w') as f:
        f.write(response.text)
    lines = response.text.split('\n')


transits = [l for l in lines if l.startswith("<tr valign='top'>")]

def xpath(root, x):
    l = root.xpath(x)
    assert len(l) <= 1
    if l:
        return l[0]
    else:
        return None

def score(data):
    min_altitude = min(data['begin_ele'], data['mid_ele'], data['end_ele'])
    if min_altitude < ALT_MIN:
        alt_score = 0
    else:
        alt_score = 1 - (90-min_altitude)/(90-ALT_MIN)
    print (f"min alt {min_altitude}, score {alt_score}")
    
    if data['delta-mag'] > 0.005:
        dmag_score = data['delta-mag'] * 33
    else:
        dmag_score = 0
    print (f"dmag {data['delta-mag']}, score {dmag_score}")

    # dur_score = min(1, 1/(data['duration'] / 60))
    # print (f"duration {data['duration']}, score {dur_score}")
    
    begin_time = datetime.datetime.strptime(data['begin_time'],  "%H:%M")
    dusk_time = datetime.datetime(year=1900, month=1, day=1, hour=DUSK_TIME.hour, minute=DUSK_TIME.minute)
    if begin_time.hour < 12:
        dusk_score = 1
        dusk_delay = "early morning"
    else:
        dusk_delay = begin_time - dusk_time
        dusk_hours = dusk_delay.days*24 + (dusk_delay.seconds/60/60)
        if dusk_hours < 1:
            dusk_score = max(0, dusk_hours)
        else:
            dusk_score = 1
    print (f"start {data['begin_time']}, dusk-delay {dusk_delay}, dusk-score {dusk_score}")
  
    end_time = datetime.datetime.strptime(data['end_time'], "%H:%M").time()
    print(end_time)
    if end_time.hour > 12:
        end_score = 1
    elif end_time.hour >= END_CUTOFF_HOUR:
        end_score = 0
    else:
        end_score = 1 - (end_time.hour + (end_time.minute / 60)) / END_CUTOFF_HOUR
    print (f"end time {end_time}, score {end_score}")

    # actual mag
    mag = int(data['mag'])
    if mag > 14:
        mag_score = 0
    elif mag < 10:
        mag_score = 1
    else:
        mag_score = 1 - (mag-10)/4
    print (f"magnitude {mag} score {mag_score}")

    # moon
    scores = [end_score, dusk_score, dmag_score, alt_score, mag_score]
    print (scores)
    score = end_score * dusk_score * dmag_score * alt_score * mag_score
    print(score)
    data['score'] = f"{score:.3f}"

    print()

def parse_transit(html):
    if "predict_detail" not in html:
        return

    # <tr valign='top'><td><b><a href='predict_detail.php?STARNAME=WASP-12&PLANET=b&delka=17&sirka=17'>WASP-12&nbsp;b</a></b>
    # <p style='text-align: right; margin: 0pt;'>Aur</p></td><td class='center'>2:21<br>56°,NE</td><td class='center'>
    # <b>01.10. 3:51<br>73°,NE</b></td><td class='center'>5:21<br>75°,NW</td><td class='center'>180.06</td><td class='center'>
    # 11.69</td><td class='center'>0.0151</td><td><span style='font-size: 80%'>56594.6816+1.09141964*E<br/>RA: 06 30 32.79<br/>
    # DE: +29 40 20.4</span></td></tr>

    root = lxml.html.fromstring(html)
    data = OrderedDict()
    data['url'] = 'http://var2.astro.cz/ETD/' + xpath(root, '//a/@href')
    planet_name = xpath(root, '//a/text()')
    data['planet'] = planet_name.replace('\xa0', ' ')
    data['constellation'] = xpath(root, '//p/text()')
    tds = re.findall(r"<td class='center'>(.*?)</td>", html)
    
    begin_time, begin_ele, begin_dir =  re.search('(.*)<br>(.*),(.*)', tds[0]).groups()
    mid_time_date, mid_ele, mid_dir= re.search('<b>(.*)<br>(.*),(.*)</b>', tds[1]).groups()
    end_time, end_ele, end_dir = re.search('(.*)<br>(.*),(.*)', tds[2]).groups()
    data['date'], _, mid_time = mid_time_date.partition(". ")

    data['begin_time'], data['mid_time'], data['end_time'] = begin_time, mid_time, end_time
    data['begin_ele'], data['begin_dir'], data['mid_ele'], data['mid_dir'], data['end_ele'], data['end_dir'] = begin_ele, begin_dir, mid_ele, mid_dir, end_ele, end_dir
    data['duration'], data['mag'], data['delta-mag'] = map(float, tds[3:])
    span = re.search(r"<span style='font-size: 80%'>(.*?)</span>", html).group(1)
    data['elems'], data['ra'], data['dec'] = re.search('(.*)<br/>RA: (.*)<br/>DE: (.*)', span).groups()
    return data

def format_transit(data):
    day, month = map(int, data['date'].split("."))
    year = NOW.year 
    date = datetime.date(day=day, month=month, year=year)
    if data['mid_time'].index(':') == 1:
        print (f"midtime {data['mid_time']}, rewinding day")
        date = date - datetime.timedelta(days=1)
    data['date'] = datetime.datetime.strftime(date, "%d %b")
    
    data['mid_ele'] = int(data['mid_ele'].replace('\xb0', ''))
    
    data['begin_ele'] = int(data['begin_ele'].replace('\xb0', ''))
    data['end_ele'] = int(data['end_ele'].replace('\xb0', ''))
    return data

with open("exoplanets.csv", "w") as outfile:
    csvwriter = csv.writer(outfile)
    first = True
    for t in transits:
        data = parse_transit(t)
        if data:
            data = format_transit(data)
            score(data)
            if first:
                csvwriter.writerow(dict(data))
                first = False
            csvwriter.writerow(dict(data).values())