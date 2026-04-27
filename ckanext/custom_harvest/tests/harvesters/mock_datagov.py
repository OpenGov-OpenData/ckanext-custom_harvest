from __future__ import print_function

import json
import re
from urllib.parse import unquote_plus

from threading import Thread

from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer


PORT = 8999


class MockDataGovHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/search'):
            params = self.get_url_params()

            # Simulate cursor-based pagination
            after = params.get('after')

            if not after:
                # First page - return first 2 datasets
                results = DATASETS[:2]
                after_cursor = 'page2_cursor'
            elif after == 'page2_cursor':
                # Second page - return remaining datasets, no more pages
                results = DATASETS[2:]
                after_cursor = None
            else:
                # Unknown cursor
                results = []
                after_cursor = None

            response = {
                'results': results,
                'total': len(DATASETS)
            }

            if after_cursor:
                response['after'] = after_cursor

            return self.respond_json(response)

        self.respond('Mock Data.gov doesnt recognize that call', status=400)

    def get_url_params(self):
        if '?' not in self.path:
            return {}
        params_str = self.path.split('?')[-1]
        params_unicode = unquote_plus(params_str)
        params = params_unicode.split('&')
        return dict([param.split('=', 1) for param in params if '=' in param])

    def respond_json(self, content_dict, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(content_dict).encode('utf-8'))
        self.wfile.close()

    def respond(self, content, status=200, content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))
        self.wfile.close()

    def log_message(self, format, *args):
        # Suppress request logging to avoid cluttering test output
        pass


def serve(port=PORT):
    '''Runs a Data.gov-alike app (over HTTP) that is used for harvesting tests'''

    class TestServer(TCPServer):
        allow_reuse_address = True

    httpd = TestServer(('', PORT), MockDataGovHandler)

    print('Serving test Data.gov HTTP server at port {}'.format(PORT))

    httpd_thread = Thread(target=httpd.serve_forever)
    httpd_thread.setDaemon(True)
    httpd_thread.start()


# Sample datasets in Data.gov Search API format
DATASETS = [
    {
        'identifier': 'dataset1-uuid-12345678-1234-1234-1234-123456789012',
        'slug': 'test-water-quality-dataset-1',
        'title': 'Water Quality Monitoring Data 2020-2025',
        'description': 'Comprehensive water quality monitoring data from EPA monitoring stations across California.',
        'publisher': 'Environmental Protection Agency',
        'keyword': ['environment', 'water', 'quality', 'monitoring', 'california'],
        'theme': ['Environment'],
        'has_spatial': True,
        'popularity': 85,
        'last_harvested_date': '2026-04-20T10:00:00Z',
        'distribution_titles': ['Water Quality CSV', 'Water Quality API'],
        'organization': {
            'id': 'org1-epa-id',
            'name': 'epa-gov',
            'slug': 'epa-gov',
            'organization_type': 'Federal Government',
            'logo': 'https://www.epa.gov/sites/all/themes/epa/logo.png',
            'aliases': ['EPA', 'Environmental Protection Agency']
        },
        'dcat': {
            'accessLevel': 'public',
            'modified': '2026-04-15T12:00:00Z',
            'issued': '2020-01-15T00:00:00Z',
            'contactPoint': {
                'fn': 'John Doe',
                'hasEmail': 'mailto:john.doe@epa.gov'
            },
            'license': 'https://creativecommons.org/publicdomain/zero/1.0/',
            'rights': 'This dataset is in the public domain.',
            'spatial': '-127.00000000,32.50000000,-114.10000000,42.00000000',
            'temporal': '2020-01-01/2026-01-01',
            'bureauCode': ['020:00'],
            'programCode': ['020:072'],
            'theme': ['Environment'],
            'landingPage': 'https://www.epa.gov/waterdata/water-quality',
            'accrualPeriodicity': 'R/P1M',
            'distribution': [
                {
                    'title': 'Water Quality Data CSV',
                    'description': 'Downloadable CSV file with water quality measurements',
                    'downloadURL': 'https://www.epa.gov/sites/default/files/water-quality.csv',
                    'mediaType': 'text/csv',
                    'format': 'CSV',
                    'byteSize': 1024000
                },
                {
                    'title': 'Water Quality API',
                    'description': 'RESTful API endpoint for programmatic access',
                    'accessURL': 'https://api.epa.gov/water-quality',
                    'mediaType': 'application/json',
                    'format': 'JSON'
                }
            ]
        },
        'harvest_record': 'https://catalog.data.gov/harvest/object/dataset1-uuid-12345678-1234-1234-1234-123456789012',
        'harvest_record_raw': 'https://catalog.data.gov/harvest/raw/dataset1-uuid-12345678-1234-1234-1234-123456789012',
        'spatial_shape': {
            'type': 'Polygon',
            'coordinates': [[[-127.0, 32.5], [-127.0, 42.0], [-114.1, 42.0], [-114.1, 32.5], [-127.0, 32.5]]]
        },
        'spatial_centroid': {
            'lat': 37.25,
            'lon': -120.55
        }
    },
    {
        'identifier': 'dataset2-uuid-abcdefab-abcd-abcd-abcd-abcdefabcdef',
        'slug': 'fish-wildlife-survey-2025',
        'title': 'Fish and Wildlife Population Survey 2025',
        'description': 'Annual survey of fish and wildlife populations in California coastal regions.',
        'publisher': 'U.S. Fish and Wildlife Service',
        'keyword': ['fish', 'wildlife', 'survey', 'population', 'california'],
        'theme': ['Environment', 'Biology'],
        'has_spatial': True,
        'popularity': 72,
        'last_harvested_date': '2026-04-21T08:30:00Z',
        'distribution_titles': ['Survey Results PDF', 'GeoJSON Data'],
        'organization': {
            'id': 'org2-fws-id',
            'name': 'fws-gov',
            'slug': 'fws-gov',
            'organization_type': 'Federal Government',
            'logo': 'https://www.fws.gov/logo.png',
            'aliases': ['FWS', 'U.S. Fish and Wildlife Service']
        },
        'dcat': {
            'accessLevel': 'public',
            'modified': '2026-04-18T14:20:00Z',
            'contactPoint': {
                'fn': 'Jane Smith',
                'hasEmail': 'mailto:jane.smith@fws.gov'
            },
            'license': 'https://creativecommons.org/licenses/by/4.0/',
            'spatial': '-124.50000000,32.50000000,-114.10000000,42.00000000',
            'temporal': '2025-01-01/2025-12-31',
            'bureauCode': ['010:18'],
            'programCode': ['010:094'],
            'theme': ['Environment', 'Biology'],
            'landingPage': 'https://www.fws.gov/program/fisheries',
            'distribution': [
                {
                    'title': 'Survey Results Report',
                    'description': 'Complete survey results and analysis',
                    'downloadURL': 'https://www.fws.gov/sites/default/files/survey-2025.pdf',
                    'mediaType': 'application/pdf',
                    'format': 'PDF',
                    'byteSize': 5242880
                },
                {
                    'title': 'Population Data GeoJSON',
                    'description': 'Geographic population distribution data',
                    'downloadURL': 'https://www.fws.gov/sites/default/files/population.geojson',
                    'mediaType': 'application/geo+json',
                    'format': 'GeoJSON',
                    'byteSize': 2097152
                }
            ]
        },
        'harvest_record': 'https://catalog.data.gov/harvest/object/dataset2-uuid-abcdefab-abcd-abcd-abcd-abcdefabcdef',
        'harvest_record_raw': 'https://catalog.data.gov/harvest/raw/dataset2-uuid-abcdefab-abcd-abcd-abcd-abcdefabcdef',
        'spatial_shape': {
            'type': 'Polygon',
            'coordinates': [[[-124.5, 32.5], [-124.5, 42.0], [-114.1, 42.0], [-114.1, 32.5], [-124.5, 32.5]]]
        },
        'spatial_centroid': {
            'lat': 37.25,
            'lon': -119.3
        }
    },
    {
        'identifier': 'dataset3-uuid-99999999-9999-9999-9999-999999999999',
        'slug': 'air-quality-index-data',
        'title': 'Daily Air Quality Index 2024-2026',
        'description': 'Daily air quality index measurements from monitoring stations nationwide.',
        'publisher': 'Environmental Protection Agency',
        'keyword': ['air', 'quality', 'aqi', 'pollution', 'environment'],
        'theme': ['Environment', 'Health'],
        'has_spatial': False,
        'popularity': 95,
        'last_harvested_date': '2026-04-22T06:00:00Z',
        'distribution_titles': ['AQI Data API'],
        'organization': {
            'id': 'org1-epa-id',
            'name': 'epa-gov',
            'slug': 'epa-gov',
            'organization_type': 'Federal Government',
            'logo': 'https://www.epa.gov/sites/all/themes/epa/logo.png',
            'aliases': ['EPA', 'Environmental Protection Agency']
        },
        'dcat': {
            'accessLevel': 'public',
            'modified': '2026-04-22T00:00:00Z',
            'contactPoint': {
                'fn': 'Air Quality Team',
                'hasEmail': 'mailto:airquality@epa.gov'
            },
            'license': 'http://www.opendefinition.org/licenses/cc-zero',
            'temporal': '2024-01-01/2026-12-31',
            'bureauCode': ['020:00'],
            'programCode': ['020:033'],
            'theme': ['Environment', 'Health'],
            'landingPage': 'https://www.epa.gov/outdoor-air-quality-data',
            'accrualPeriodicity': 'R/P1D',
            'distribution': [
                {
                    'title': 'AQI Data API',
                    'description': 'Real-time air quality index data API',
                    'accessURL': 'https://api.epa.gov/air-quality/aqi',
                    'mediaType': 'application/json',
                    'format': 'API'
                },
                {
                    'title': 'Historical AQI Data',
                    'description': 'Historical air quality measurements',
                    'downloadURL': 'https://www.epa.gov/sites/default/files/aqi-historical.xlsx',
                    'mediaType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    'format': 'XLSX',
                    'byteSize': 15728640
                }
            ]
        },
        'harvest_record': 'https://catalog.data.gov/harvest/object/dataset3-uuid-99999999-9999-9999-9999-999999999999',
        'harvest_record_raw': 'https://catalog.data.gov/harvest/raw/dataset3-uuid-99999999-9999-9999-9999-999999999999'
    }
]
