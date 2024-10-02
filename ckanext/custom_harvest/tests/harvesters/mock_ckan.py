from __future__ import print_function

import json
import re
import copy
from urllib.parse import unquote_plus

from threading import Thread

from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer


PORT = 8998


class MockCkanHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        # test name is the first bit of the URL and makes CKAN behave
        # differently in some way.
        # Its value is recorded and then removed from the path
        self.test_name = None
        test_name_match = re.match('^/([^/]+)/', self.path)
        if test_name_match:
            self.test_name = test_name_match.groups()[0]
            if self.test_name == 'api':
                self.test_name = None
            else:
                self.path = re.sub('^/([^/]+)/', '/', self.path)
        if self.test_name == 'site_down':
            return self.respond('Site is down', status=500)

        # The API version is recorded and then removed from the path
        api_version = None
        version_match = re.match(r'^/api/(\d)', self.path)
        if version_match:
            api_version = int(version_match.groups()[0])
            self.path = re.sub(r'^/api/(\d)/', '/api/', self.path)

        if self.path == '/api/action/package_list':
            dataset_names = [d['name'] for d in DATASETS]
            return self.respond_action(dataset_names)
        if self.path.startswith('/api/action/package_show'):
            params = self.get_url_params()
            dataset_ref = params['id']
            dataset = self.get_dataset(dataset_ref)
            if dataset:
                return self.respond_action(dataset)
        # /api/3/action/package_search?fq=metadata_modified:[2015-10-23T14:51:13.282361Z TO *]&rows=1000
        if self.path.startswith('/api/action/package_search'):
            params = self.get_url_params()

            # ignore sort param for now
            if 'sort' in params:
                del params['sort']
            if params['start'] != '0':
                datasets = []
            elif set(params.keys()) == set(['rows', 'start']):
                datasets = ['dataset1', DATASETS[1]['name']]
            elif set(params.keys()) == set(['fq', 'rows', 'start']) and \
                    params['fq'] == '-organization:org1':
                datasets = [DATASETS[1]['name']]
            elif set(params.keys()) == set(['fq', 'rows', 'start']) and \
                    params['fq'] == 'organization:org1':
                datasets = ['dataset1']
            elif set(params.keys()) == set(['fq', 'rows', 'start']) and \
                    params['fq'] == '-groups:group1':
                datasets = [DATASETS[1]['name']]
            elif set(params.keys()) == set(['fq', 'rows', 'start']) and \
                    params['fq'] == 'groups:group1':
                datasets = ['dataset1']
            elif set(params.keys()) == set(['fq', 'rows', 'start']) and \
                    'metadata_modified' in params['fq']:
                assert '+TO+' not in params['fq'], \
                    'Spaces should not be decoded by now - seeing + '\
                    'means they were double encoded and SOLR doesnt like '\
                    'that'
                datasets = [DATASETS[1]['name']]
            elif set(params.keys()) == set(['tags', 'rows', 'start']) and \
                    params['tags'] == 'test-tag':
                    datasets = [DATASETS[0]['name'], DATASETS[1]['name']]
            else:
                return self.respond(
                    'Not implemented search params %s' % params,
                    status=400)

            out = {'count': len(datasets),
                   'results': [self.get_dataset(dataset_ref_)
                               for dataset_ref_ in datasets]}
            return self.respond_action(out)

        # if we wanted to server a file from disk, then we'd call this:
        # return SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

        self.respond('Mock CKAN doesnt recognize that call', status=400)

    def get_dataset(self, dataset_ref):
        for dataset in DATASETS:
            if dataset['name'] == dataset_ref or \
                    dataset['id'] == dataset_ref:
                return dataset

    def get_url_params(self):
        params_str = self.path.split('?')[-1]
        params_unicode = unquote_plus(params_str)
        params = params_unicode.split('&')
        return dict([param.split('=') for param in params])

    def respond_action(self, result_dict, status=200):
        response_dict = {'result': result_dict, 'success': True}
        return self.respond_json(response_dict, status=status)

    def respond_json(self, content_dict, status=200):
        return self.respond(json.dumps(content_dict), status=status,
                            content_type='application/json')

    def respond(self, content, status=200, content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))
        self.wfile.close()


def serve(port=PORT):
    '''Runs a CKAN-alike app (over HTTP) that is used for harvesting tests'''

    # Choose the directory to serve files from
    # os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)),
    #                      'mock_ckan_files'))

    class TestServer(TCPServer):
        allow_reuse_address = True

    httpd = TestServer(('', PORT), MockCkanHandler)

    print('Serving test HTTP server at port {}'.format(PORT))

    httpd_thread = Thread(target=httpd.serve_forever)
    httpd_thread.setDaemon(True)
    httpd_thread.start()


def convert_dataset_to_restful_form(dataset):
    dataset = copy.deepcopy(dataset)
    dataset['extras'] = dict([(e['key'], e['value']) for e in dataset['extras']])
    dataset['tags'] = [t['name'] for t in dataset.get('tags', [])]
    return dataset


# Datasets are in the package_show form, rather than the RESTful form
DATASETS = [
    {
        'id': 'dataset1-id',
        'name': 'dataset1',
        'title': 'Test Dataset1',
        'organization': {
            'id': '0f8380d6-241a-47de-aa52-8bd91c763d97',
            'name': 'org1',
            'title': 'Test Org1'
        },
        'owner_org': '0f8380d6-241a-47de-aa52-8bd91c763d97',
        'tags': [
            {
                'name': 'test-tag'
            }
        ],
        'groups': [
            {
                'id': '10037fa4-e683-4a67-892a-efba815e24ad',
                'name': 'group1',
                'title': 'Test Group1'
            }
        ],
        'resources': [
            {
                'id': 'resource1-id',
                'name': 'Test Resource 1',
                'url': 'http://test.gov/test1.csv',
                'format': 'CSV',
                'position': 0
            }
        ],
        'extras': []
    },
    {
        'id': 'dataset2-id',
        'name': 'dataset2',
        'title': 'Test Dataset2',
        'organization': {
            'id': 'aa1e068a-23da-4563-b9c2-2cad272b663e',
            'name': 'org2',
            'title': 'Test Org2'
        },
        'owner_org': 'aa1e068a-23da-4563-b9c2-2cad272b663e',
        'tags': [
            {
                'name': 'test-tag'
            }
        ],
        'groups': [
            {
                'id': '9853c3e1-eebb-4e8c-9ae7-1668a01bf2ca',
                'name': 'group2',
                'title': 'Test Group2'
            }
        ],
        'resources': [
            {
                'id': 'resource2-id',
                'name': 'Test Resource 2',
                'url': 'http://test.gov/test2.csv',
                'format': 'CSV',
                'position': 0
            }
        ],
        'extras': []
    }
]