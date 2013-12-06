import requests
import json

base_url = 'http://gisweb.co.aitkin.mn.us/arcgis/rest/services/MapLayers/MapServer/3'
output_file = 'output.geojson'

metadata = requests.get(base_url, params={'f': 'json'}).json()
bounds = metadata['extent']
fields = metadata['fields']
geom_type = metadata['geometryType']
saved = set()

# Look for a field that to use as the deduping ID
oid_field = next(field['name'] for field in fields if field['type'] == 'esriFieldTypeOID')

if oid_field:
    print "Using '%s' as the OID field to dedupe." % oid_field
else:
    print "WARNING: Couldn't find the OID field to dedupe on, so you'll have duplicate data probably."

cells_x = 5
cells_y = 5
x_step = (bounds['xmax'] - bounds['xmin']) / cells_x
y_step = (bounds['ymax'] - bounds['ymin']) / cells_y

def xfrange(start, stop=None, step=None):
    """Like range(), but returns list of floats instead

    All numbers are generated on-demand using generators
    """

    if stop is None:
        stop = float(start)
        start = 0.0

    if step is None:
        step = 1.0

    cur = float(start)

    while cur < stop:
        yield cur
        cur += step

def esrijson2geojson(geom_type, esrijson):
    geojson = {}
    if geom_type == 'esriGeometryPolygon':
        geojson['type'] = 'Polygon'
        geojson['coordinates'] = esrijson['rings']
    elif geom_type == 'esriGeometryPolyline':
        geojson['type'] = 'MultiLineString'
        geojson['coordinates'] = esrijson['paths']
    elif geom_type == 'esriGeometryPoint':
        geojson['type'] = 'Point'
        geojson['coordinates'] = [esrijson['x'], esrijson['y']]
    else:
        print "I don't know how to convert esrijson of type '%s'." % geom_type

    return geojson

i = 0

f = open(output_file, 'w')
f.write("""{
    "type": "FeatureCollection",
    "features": [\n""")

for x in xfrange(bounds['xmin'], bounds['xmax'], x_step):
    for y in xfrange(bounds['ymin'], bounds['ymax'], y_step):
        bbox = (x, y, x + x_step, y + y_step)

        geometry = json.dumps({
            "rings": [
                [
                    [bbox[0], bbox[1]],
                    [bbox[0], bbox[3]],
                    [bbox[2], bbox[3]],
                    [bbox[2], bbox[1]],
                    [bbox[0], bbox[1]]
                ]
            ]
        })

        args = {
            'geometry': geometry,
            'geometryType': 'esriGeometryPolygon',
            'inSR': bounds['spatialReference']['wkid'],
            'spatialRel': 'esriSpatialRelIntersects',
            'returnCountOnly': 'false',
            'returnIdsOnly': 'false',
            'returnGeometry': 'true',
            'outSR': 4326,
            'outFields': '*',
            'f': 'json'
        }

        resp = requests.get(base_url + '/query', params=args)
        for feature in resp.json()['features']:
            attrs = feature['attributes']

            oid = attrs.get(oid_field)

            if oid in saved:
                continue

            geom = feature['geometry']

            f.write(json.dumps({
                "type": "Feature",
                "properties": attrs,
                "geometry": esrijson2geojson(geom_type, geom)
            }))
            f.write(',\n')

            saved.add(oid)
        i += 1
        print "%s/%s cells, %s features." % (i, (cells_x * cells_y), len(saved))

f.write("]\n}\n")