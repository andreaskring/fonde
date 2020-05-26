import json
import requests
from requests.auth import HTTPBasicAuth


USERNAME = 'username'
PASSWORD = 'something secret'
URL = 'http://distribution.virk.dk/cvr-permanent/virksomhed/_search?scroll=20s'
SLICE_MAX = 3
ORG = 'organisationer'
ATTR = 'attributter'
REELLE_EJERE = 'Reelle ejere'
PERSON = 'PERSON'


def get_cvrs(data):
    hits = data['hits']['hits']
    return {
        hit['_source']['Vrvirksomhed']['cvrNummer'] for hit in hits
    }


def generate_payload(id, maximum):
    with open('fundats_scroll.json', 'r') as f:
        payload = json.load(f)
    payload['slice']['id'] = id
    payload['slice']['max'] = maximum
    return payload


def query(payload):
    return requests.post(
        URL,
        json=payload,
        auth=HTTPBasicAuth(USERNAME, PASSWORD)
    ).json()


def parse(hits):
    foundation_owners = []
    for hit in hits:
        vr_virksomhed = hit['_source']['Vrvirksomhed']

        # CVR
        cvr = vr_virksomhed['cvrNummer']

        # Get the name of the foundation
        names = vr_virksomhed['navne']
        name_list = [
            n['navn'] for n in names if n['periode']['gyldigTil'] is None
        ]
        name = name_list[0] if len(name_list) == 1 else ', '.join([
            n['navn'] for n in names
        ])

        # Get the "Reelle ejer"
        deltager_relationer = vr_virksomhed['deltagerRelation']
        reelle_ejere = []
        non_reelle_ejere = []
        for deltager_relation in deltager_relationer:
            if 'deltager' in deltager_relation:
                deltager = deltager_relation['deltager']
                if deltager and 'enhedstype' in deltager:
                    enhedstype = deltager['enhedstype']
                    if enhedstype.lower() == PERSON.lower():
                        # Make sure the "deltager" only has one name
                        assert len(deltager_relation['deltager']['navne']) == 1
                        deltager_navn = deltager_relation['deltager'][
                            'navne'][0]['navn']

                        reel_ejer = False
                        for org in deltager_relation[ORG]:
                            for org_navn in org['organisationsNavn']:
                                if org_navn['navn'].lower() == REELLE_EJERE.lower():
                                    reel_ejer = True
                        if reel_ejer:
                            reelle_ejere.append(deltager_navn)
                        else:
                            non_reelle_ejere.append(deltager_navn)
                else:
                    print('deltager null or no enhedstype')
                    # print(json.dumps(deltager_relation, indent=2))
            else:
                print('deltager not found in deltager_relation')
                print(json.dumps(deltager_relation, indent=2))

        foundation_owners.append(
            (cvr, name, reelle_ejere, non_reelle_ejere)
        )

    return foundation_owners


data = [query(generate_payload(i, SLICE_MAX)) for i in range(SLICE_MAX)]
cvrs = [get_cvrs(data[i]) for i in range(SLICE_MAX)]

# Make sure all results (CVR numbers) are distinct
assert cvrs[0].isdisjoint(cvrs[1]) and \
       cvrs[0].isdisjoint(cvrs[2]) and \
       cvrs[1].isdisjoint(cvrs[2])

foundation_owners = []
for i in range(SLICE_MAX):
    foundation_owners += parse(data[i]['hits']['hits'])

# with open('fonde_all.csv', 'w') as fp:
#     for cvr, name, reelle_ejere, others in foundation_owners:
#         fp.write('{};{};{};;{}\n'.format(cvr, name, ';'.join(reelle_ejere), ';'.join(others)))
