import os
import json
import difflib
from ckanext.custom_harvest.converter import package_search_to_ckan


def _get_file_as_dict(file_name):
    path = os.path.join(os.path.dirname(__file__), 'examples', file_name)
    with open(path, 'r') as f:
        return json.load(f)

def _poor_mans_dict_diff(d1, d2):
    def _get_lines(d):
        return sorted([l.strip().rstrip(',')
                       for l in json.dumps(d, indent=0).split('\n')
                       if not l.startswith(('{', '}', '[', ']'))])

    d1_lines = _get_lines(d1)
    d2_lines = _get_lines(d2)

    return '\n' + '\n'.join([l for l in difflib.ndiff(d1_lines, d2_lines)
                             if l.startswith(('-', '+'))])

def test_package_search_to_ckan():
    package_search_dict =_get_file_as_dict('package_search.json')
    expected_ckan_dict =_get_file_as_dict('ckan_dataset.json')

    ckan_dict = package_search_to_ckan(package_search_dict)

    assert ckan_dict == expected_ckan_dict,_poor_mans_dict_diff(
        expected_ckan_dict, ckan_dict)
