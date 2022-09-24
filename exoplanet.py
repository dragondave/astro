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
    data['url'] = xpath(root, '//a/@href')
    planet_name = xpath(root, '//a/text()')
    data['planet'] = planet_name.replace('\xa0', ' ')
    data['constellation'] = xpath(root, '//p/text()')
    tds = re.findall(r"<td class='center'>(.*?)</td>", html)
    data['begin_time'], data['begin_elevation'], data['begin_dir'] = re.search('(.*)<br>(.*),(.*)', tds[0]).groups()
    data['mid_time'], data['mid_elevation'], data['mid_dir'] = re.search('<b>(.*)<br>(.*),(.*)</b>', tds[1]).groups()
    data['end_time'], data['end_elevation'], data['end_dir'] = re.search('(.*)<br>(.*),(.*)', tds[2]).groups()
    data['duration'], data['mag'], data['delta-mag'] = tds[3:]
    span = re.search(r"<span style='font-size: 80%'>(.*?)</span>", html).group(1)
    data['elems'], data['ra'], data['dec'] = re.search('(.*)<br/>RA: (.*)<br/>DE: (.*)', span).groups()
    return data



with open("exoplanets.csv", "w") as outfile:
    csvwriter = csv.writer(outfile)
    first = True
    for t in transits:
        data = parse_transit(t)
        if data and first:
            csvwriter.writerow(dict(data))
            first = False
        if data:
            csvwriter.writerow(dict(data).values())