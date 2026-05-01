from __future__ import absolute_import

import json
import pytest

from ckantoolkit.tests.factories import Organization

from ckanext.harvest.tests.factories import (HarvestSourceObj, HarvestJobObj,
                                             HarvestObjectObj)
from ckanext.harvest.model import HarvestObjectExtra
from ckanext.harvest.tests.lib import run_harvest_job
import ckanext.harvest.model as harvest_model

from ckanext.custom_harvest.harvesters.datagov import (
    DataGovHarvester,
    _source_groups_from_datagov_themes,
)
from ckanext.custom_harvest.tests.harvesters import mock_datagov


# Start Data.gov-alike server we can test harvesting against it
mock_datagov.serve()


@pytest.mark.usefixtures('with_plugins', 'clean_db', 'clean_index')
class TestDataGovHarvester(object):

    def test_gather_normal(self):
        source = HarvestSourceObj(
            url='http://localhost:%s/search?q=water' % mock_datagov.PORT
        )
        job = HarvestJobObj(source=source)

        harvester = DataGovHarvester()
        obj_ids = harvester.gather_stage(job)

        assert job.gather_errors == []
        assert isinstance(obj_ids, list)
        assert len(obj_ids) == len(mock_datagov.DATASETS)
        harvest_object = harvest_model.HarvestObject.get(obj_ids[0])
        assert harvest_object.guid == mock_datagov.DATASETS[0]['identifier']
        assert json.loads(harvest_object.content) == mock_datagov.DATASETS[0]

    def test_gather_with_cursor_pagination(self):
        '''Test that cursor-based pagination works correctly'''
        source = HarvestSourceObj(
            url='http://localhost:%s/search' % mock_datagov.PORT
        )
        job = HarvestJobObj(source=source)

        harvester = DataGovHarvester()
        obj_ids = harvester.gather_stage(job)

        # Should get all datasets across multiple pages
        assert len(obj_ids) == len(mock_datagov.DATASETS)
        assert job.gather_errors == []

    def test_fetch_normal(self):
        source = HarvestSourceObj(
            url='http://localhost:%s/search' % mock_datagov.PORT
        )
        job = HarvestJobObj(source=source)
        harvest_object = HarvestObjectObj(
            guid=mock_datagov.DATASETS[0]['identifier'],
            job=job,
            content=json.dumps(mock_datagov.DATASETS[0]))

        harvester = DataGovHarvester()
        result = harvester.fetch_stage(harvest_object)

        assert harvest_object.errors == []
        assert result is True

    def test_import_normal(self):
        org = Organization()
        harvest_object = HarvestObjectObj(
            guid=mock_datagov.DATASETS[0]['identifier'],
            content=json.dumps(mock_datagov.DATASETS[0]),
            job__source__owner_org=org['id'])

        harvester = DataGovHarvester()
        result = harvester.import_stage(harvest_object)

        assert harvest_object.errors == []
        assert result is True
        assert harvest_object.guid

    def test_harvest_full(self):
        '''Test complete harvest cycle'''
        source = HarvestSourceObj(
            url='http://localhost:%s/search' % mock_datagov.PORT,
            config='',
            source_type='test'
        )
        job = HarvestJobObj(source=source, run=False)
        results_by_guid = run_harvest_job(job, DataGovHarvester())

        for dataset in mock_datagov.DATASETS:
            result = results_by_guid[dataset['identifier']]
            assert result['state'] == 'COMPLETE'
            assert result['errors'] == []

    def test_import_creates_correct_metadata(self):
        '''Test that DCAT-US metadata is correctly mapped'''
        org = Organization()
        harvest_object = HarvestObjectObj(
            guid=mock_datagov.DATASETS[0]['identifier'],
            content=json.dumps(mock_datagov.DATASETS[0]),
            job__source__owner_org=org['id']
        )

        # Add status extra
        extra = HarvestObjectExtra(object=harvest_object, key='status', value='new')
        extra.save()

        harvester = DataGovHarvester()
        result = harvester.import_stage(harvest_object)

        assert result is True
        assert harvest_object.package_id is not None

        # Verify package was created with correct fields
        import ckan.plugins as p
        from ckan import model
        context = {'ignore_auth': True, 'model': model, 'session': model.Session}
        package = p.toolkit.get_action('package_show')(
            context, {'id': harvest_object.package_id}
        )

        assert package['title'] == mock_datagov.DATASETS[0]['title']
        assert package['notes'] == mock_datagov.DATASETS[0]['description']

        # Check tags
        tag_names = [tag['name'] for tag in package['tags']]
        assert 'environment' in tag_names
        assert 'water' in tag_names

        # Check extras
        extras_dict = {e['key']: e['value'] for e in package['extras']}
        assert extras_dict['guid'] == mock_datagov.DATASETS[0]['identifier']
        assert extras_dict['datagov_slug'] == mock_datagov.DATASETS[0]['slug']
        assert 'spatial' in extras_dict
        assert extras_dict['publisher'] == mock_datagov.DATASETS[0]['publisher']
        assert extras_dict['contact_name'] == 'John Doe'
        assert extras_dict['contact_email'] == 'john.doe@epa.gov'
        assert extras_dict['dcat_rights'] == 'This dataset is in the public domain.'

        # Check resources
        assert len(package['resources']) == 2
        assert package['resources'][0]['format'] == 'CSV'
        assert package['resources'][0]['name'] == 'Water Quality Data CSV'
        assert package['resources'][1]['format'] == 'JSON'
        assert package['resources'][1]['name'] == 'Water Quality API'

    def test_query_parameters(self):
        '''Test that all query parameters are preserved during harvest'''
        source = HarvestSourceObj(
            url='http://localhost:%s/search?q=fish&org_slug=epa&keyword=California&spatial_within=false&spatial_geometry={"type":"Polygon","coordinates":[[[-127.0,32.5],[-127.0,42.0],[-114.1,42.0],[-114.1,32.5],[-127.0,32.5]]]}' % mock_datagov.PORT
        )
        job = HarvestJobObj(source=source)

        harvester = DataGovHarvester()
        obj_ids = harvester.gather_stage(job)

        # Should successfully parse all parameters and fetch datasets
        assert job.gather_errors == []
        assert isinstance(obj_ids, list)

    def test_organizations_filter_include(self):
        '''Test organizations_filter_include configuration'''
        source = HarvestSourceObj(
            url='http://localhost:%s/search' % mock_datagov.PORT,
            config='{"organizations_filter_include": ["epa-gov"]}'
        )
        job = HarvestJobObj(source=source)

        harvester = DataGovHarvester()
        obj_ids = harvester.gather_stage(job)

        # Should only get datasets from EPA (dataset1 and dataset3 are from epa-gov)
        assert job.gather_errors == []
        assert len(obj_ids) == 2

    def test_organizations_filter_exclude(self):
        '''Test organizations_filter_exclude configuration'''
        source = HarvestSourceObj(
            url='http://localhost:%s/search' % mock_datagov.PORT,
            config='{"organizations_filter_exclude": ["epa-gov"]}'
        )
        job = HarvestJobObj(source=source)

        harvester = DataGovHarvester()
        obj_ids = harvester.gather_stage(job)

        # Should only get datasets NOT from EPA (dataset2 is from fws-gov)
        assert job.gather_errors == []
        assert len(obj_ids) == 1


class TestTrimDate(object):
    def test_trim_midnight_timestamps(self):
        '''Test that midnight timestamps are trimmed to date only'''
        from ckanext.custom_harvest.converter import trim_date

        assert trim_date('2015-10-02T00:00:00.000+00:00') == '2015-10-02'
        assert trim_date('2015-10-02T00:00:00Z') == '2015-10-02'
        assert trim_date('2015-10-02T00:00:00') == '2015-10-02'

    def test_keep_non_midnight_timestamps(self):
        '''Test that non-midnight timestamps are kept as-is'''
        from ckanext.custom_harvest.converter import trim_date

        assert trim_date('2015-10-02T14:30:00.000+00:00') == '2015-10-02T14:30:00.000+00:00'
        assert trim_date('2026-04-15T12:00:00Z') == '2026-04-15T12:00:00Z'

    def test_date_only_unchanged(self):
        '''Test that date-only strings pass through unchanged'''
        from ckanext.custom_harvest.converter import trim_date

        assert trim_date('2015-10-02') == '2015-10-02'
        assert trim_date('') == ''
        assert trim_date(None) is None


class TestDataGovConverter(object):
    def test_datagov_to_ckan_basic(self):
        '''Test basic conversion of Data.gov format to CKAN'''
        from ckanext.custom_harvest.converter import datagov_to_ckan

        source_dict = mock_datagov.DATASETS[0]
        ckan_dict = datagov_to_ckan(source_dict)

        assert ckan_dict['title'] == source_dict['title']
        assert ckan_dict['notes'] == source_dict['description']
        assert len(ckan_dict['tags']) > 0
        assert len(ckan_dict['resources']) > 0

    def test_datagov_to_ckan_resources(self):
        '''Test distribution to resource mapping'''
        from ckanext.custom_harvest.converter import datagov_to_ckan

        source_dict = mock_datagov.DATASETS[0]
        ckan_dict = datagov_to_ckan(source_dict)

        resources = ckan_dict['resources']
        assert len(resources) == 2

        # First resource (CSV)
        assert resources[0]['name'] == 'Water Quality Data CSV'
        assert resources[0]['url'] == 'https://www.epa.gov/sites/default/files/water-quality.csv'
        assert resources[0]['format'] == 'CSV'
        assert resources[0]['mimetype'] == 'text/csv'

        # Second resource (JSON API)
        assert resources[1]['format'] == 'JSON'
        assert resources[1]['url'] == 'https://api.epa.gov/water-quality'

    def test_datagov_to_ckan_extras(self):
        '''Test that DCAT extras are correctly mapped'''
        from ckanext.custom_harvest.converter import datagov_to_ckan

        source_dict = mock_datagov.DATASETS[0]
        ckan_dict = datagov_to_ckan(source_dict)

        extras_dict = {e['key']: e['value'] for e in ckan_dict['extras']}

        # Core identifiers
        assert extras_dict['guid'] == source_dict['identifier']
        assert extras_dict['datagov_slug'] == source_dict['slug']

        # DCAT fields
        assert extras_dict['dcat_access_level'] == 'public'
        assert extras_dict['dcat_issued'] == '2020-01-15'
        assert extras_dict['contact_name'] == 'John Doe'
        assert extras_dict['contact_email'] == 'john.doe@epa.gov'
        assert 'spatial' in extras_dict
        assert extras_dict['temporal'] == '2020-01-01/2026-01-01'
        assert extras_dict['landing_page'] == 'https://www.epa.gov/waterdata/water-quality'
        assert extras_dict['dcat_rights'] == 'This dataset is in the public domain.'

    def test_datagov_to_ckan_license_mapping(self):
        '''Test license URL mapping'''
        from ckanext.custom_harvest.converter import datagov_to_ckan

        source_dict = mock_datagov.DATASETS[0]
        ckan_dict = datagov_to_ckan(source_dict)

        # CC0 license should be mapped
        assert ckan_dict.get('license_id') == 'cc-zero'

    def test_datagov_to_ckan_tags(self):
        '''Test tag sanitization'''
        from ckanext.custom_harvest.converter import datagov_to_ckan

        source_dict = mock_datagov.DATASETS[0]
        ckan_dict = datagov_to_ckan(source_dict)

        tag_names = [tag['name'] for tag in ckan_dict['tags']]

        # Check that keywords are converted to tags
        assert 'environment' in tag_names
        assert 'water' in tag_names
        assert 'quality' in tag_names
        assert 'monitoring' in tag_names
        assert 'california' in tag_names

    def test_extract_format(self):
        '''Test format extraction from distribution'''
        from ckanext.custom_harvest.converter import extract_format

        # Format field present
        dist1 = {'format': 'CSV'}
        assert extract_format(dist1) == 'CSV'

        # MediaType only
        dist2 = {'mediaType': 'text/csv'}
        assert extract_format(dist2) == 'CSV'

        # URL extension
        dist3 = {'downloadURL': 'https://example.com/data.geojson'}
        assert extract_format(dist3) == 'GEOJSON'

        # No format info
        dist4 = {'accessURL': 'https://example.com/api'}
        assert extract_format(dist4) == ''

    def test_map_datagov_license(self):
        '''Test license mapping function'''
        from ckanext.custom_harvest.converter import map_datagov_license

        # CC0
        assert map_datagov_license('https://creativecommons.org/publicdomain/zero/1.0/') == 'cc-zero'
        assert map_datagov_license('http://www.opendefinition.org/licenses/cc-zero') == 'cc-zero'

        # CC-BY
        assert map_datagov_license('https://creativecommons.org/licenses/by/4.0/') == 'cc-by'

        # Unknown license
        assert map_datagov_license('https://example.com/custom-license') is None

    def test_munge_tag(self):
        '''Test tag sanitization function'''
        from ckanext.custom_harvest.converter import munge_tag

        # Normal tag
        assert munge_tag('environment') == 'environment'

        # Tag with spaces
        assert munge_tag('water quality') == 'water quality'

        # Tag with invalid characters
        assert munge_tag('tag@with#invalid$chars') == 'tagwithinvalidchars'

        # Long tag (should truncate to 100 chars)
        long_tag = 'a' * 150
        assert len(munge_tag(long_tag)) == 100

    def test_datagov_to_ckan_missing_fields(self):
        '''Test handling of missing fields'''
        from ckanext.custom_harvest.converter import datagov_to_ckan

        # Minimal dataset
        source_dict = {
            'identifier': 'test-uuid',
            'title': 'Test Dataset'
        }
        ckan_dict = datagov_to_ckan(source_dict)

        # Should have defaults for required fields
        assert ckan_dict['title'] == 'Test Dataset'
        assert ckan_dict['notes'] == ''
        assert ckan_dict['tags'] == []
        assert ckan_dict['resources'] == []

    def test_datagov_to_ckan_resource_url_priority(self):
        '''Test that downloadURL is preferred over accessURL'''
        from ckanext.custom_harvest.converter import datagov_to_ckan

        source_dict = {
            'identifier': 'test-uuid',
            'title': 'Test',
            'dcat': {
                'distribution': [
                    {
                        'title': 'Resource with both URLs',
                        'downloadURL': 'https://example.com/download.csv',
                        'accessURL': 'https://example.com/access',
                        'format': 'CSV'
                    },
                    {
                        'title': 'Resource with accessURL only',
                        'accessURL': 'https://example.com/api',
                        'format': 'API'
                    }
                ]
            }
        }
        ckan_dict = datagov_to_ckan(source_dict)

        # First resource should use downloadURL
        assert ckan_dict['resources'][0]['url'] == 'https://example.com/download.csv'

        # Second resource should use accessURL
        assert ckan_dict['resources'][1]['url'] == 'https://example.com/api'

    def test_source_groups_from_datagov_themes_empty(self):
        assert _source_groups_from_datagov_themes({}) == []
        assert _source_groups_from_datagov_themes({'dcat': {}}) == []

    def test_source_groups_from_datagov_themes_top_level_and_dcat(self):
        source_dict = {
            'theme': ['Climate'],
            'dcat': {'theme': ['Science']},
        }
        groups = _source_groups_from_datagov_themes(source_dict)
        by_name = {g['name']: g['title'] for g in groups}
        assert by_name == {'climate': 'Climate', 'science': 'Science'}

    def test_source_groups_from_datagov_themes_dedupes_same_theme_string(self):
        source_dict = {
            'theme': ['Climate'],
            'dcat': {'theme': ['Climate']},
        }
        groups = _source_groups_from_datagov_themes(source_dict)
        assert groups == [{'name': 'climate', 'title': 'Climate'}]

    def test_source_groups_from_datagov_themes_skips_blank_theme(self):
        source_dict = {'theme': ['', 'Climate']}
        groups = _source_groups_from_datagov_themes(source_dict)
        assert groups == [{'name': 'climate', 'title': 'Climate'}]

    def test_source_groups_from_datagov_themes_distinct_strings_same_slug(self):
        '''Different theme strings can munge to the same group name (RemoteGroups dedupes).'''
        source_dict = {'theme': ['Economy', 'economy']}
        groups = _source_groups_from_datagov_themes(source_dict)
        assert len(groups) == 2
        assert {g['name'] for g in groups} == {'economy'}
        assert {g['title'] for g in groups} == {'Economy', 'economy'}

    def test_source_groups_from_datagov_themes_munges_multiword(self):
        source_dict = {'theme': ['Water Quality']}
        groups = _source_groups_from_datagov_themes(source_dict)
        assert groups == [{'name': 'water-quality', 'title': 'Water Quality'}]
