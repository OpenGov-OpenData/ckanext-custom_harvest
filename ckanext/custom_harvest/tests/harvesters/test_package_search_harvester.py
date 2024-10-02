from __future__ import absolute_import

import json
import pytest

from ckantoolkit.tests.factories import Organization

from ckanext.harvest.tests.factories import (HarvestSourceObj, HarvestJobObj,
                                             HarvestObjectObj)
from ckanext.harvest.tests.lib import run_harvest_job
import ckanext.harvest.model as harvest_model

from ckanext.custom_harvest.harvesters.package_search import copy_across_resource_ids, PackageSearchHarvester
from ckanext.custom_harvest.tests.harvesters  import mock_ckan


# Start CKAN-alike server we can test harvesting against it
mock_ckan.serve()


@pytest.mark.usefixtures('with_plugins', 'clean_db', 'clean_index')
class TestPackageSearchHarvester(object):

    def test_gather_normal(self):
        source = HarvestSourceObj(
            url='http://localhost:%s/api/action/package_search?tags=test-tag' % mock_ckan.PORT
        )
        job = HarvestJobObj(source=source)

        harvester = PackageSearchHarvester()
        obj_ids = harvester.gather_stage(job)

        assert job.gather_errors == []
        assert isinstance(obj_ids, list)
        assert len(obj_ids) == len(mock_ckan.DATASETS)
        harvest_object = harvest_model.HarvestObject.get(obj_ids[0])
        assert harvest_object.guid == mock_ckan.DATASETS[0]['name']
        assert json.loads(harvest_object.content) == mock_ckan.DATASETS[0]

    def test_fetch_normal(self):
        source = HarvestSourceObj(
            url='http://localhost:%s/api/action/package_search?tags=test-tag' % mock_ckan.PORT
        )
        job = HarvestJobObj(source=source)
        harvest_object = HarvestObjectObj(
            guid=mock_ckan.DATASETS[0]['name'],
            job=job,
            content=json.dumps(mock_ckan.DATASETS[0]))

        harvester = PackageSearchHarvester()
        result = harvester.fetch_stage(harvest_object)

        assert harvest_object.errors == []
        assert result is True

    def test_import_normal(self):
        org = Organization()
        harvest_object = HarvestObjectObj(
            guid=mock_ckan.DATASETS[0]['name'],
            content=json.dumps(mock_ckan.DATASETS[0]),
            job__source__owner_org=org['id'])

        harvester = PackageSearchHarvester()
        result = harvester.import_stage(harvest_object)

        assert harvest_object.errors == []
        assert result is True
        assert harvest_object.guid

    def test_harvest(self):
        source = HarvestSourceObj(
            url='http://localhost:%s/api/action/package_search?tags=test-tag' % mock_ckan.PORT,
            config='',
            source_type='test'
        )
        job = HarvestJobObj(source=source, run=False)
        results_by_guid = run_harvest_job(job, PackageSearchHarvester())

        result = results_by_guid[mock_ckan.DATASETS[0]['name']]
        assert result['state'] == 'COMPLETE'
        assert result['errors'] == []

        result = results_by_guid[mock_ckan.DATASETS[1]['name']]
        assert result['state'] == 'COMPLETE'
        assert result['errors'] == []


class TestCopyAcrossResourceIds(object):
    def test_copied_because_same_name_url_format(self):
        harvested_dataset = {'resources': [
            {'name': 'abc', 'url': 'http://abc', 'format': 'csv'}]}
        copy_across_resource_ids({'resources': [
            {'name': 'abc', 'url': 'http://abc', 'format': 'csv', 'id': '1'}]},
            harvested_dataset,
        )
        assert harvested_dataset['resources'][0].get('id') == '1'
        assert harvested_dataset['resources'][0].get('url') == 'http://abc'

    def test_copied_because_same_url(self):
        harvested_dataset = {'resources': [
            {'url': 'http://abc'}]}
        copy_across_resource_ids({'resources': [
            {'url': 'http://abc', 'id': '1'}]},
            harvested_dataset,
        )
        assert harvested_dataset['resources'][0].get('id') == '1'

    def test_copied_with_same_url_and_changed_name(self):
        harvested_dataset = {'resources': [
            {'url': 'http://abc', 'name': 'link updated'}]}
        copy_across_resource_ids({'resources': [
            {'url': 'http://abc', 'name': 'link', 'id': '1'}]},
            harvested_dataset,
        )
        assert harvested_dataset['resources'][0].get('id') == '1'

    def test_copied_with_repeated_urls_but_unique_names(self):
        harvested_dataset = {'resources': [
            {'url': 'http://abc', 'name': 'link1'},
            {'url': 'http://abc', 'name': 'link5'},
            {'url': 'http://abc', 'name': 'link3'},
            {'url': 'http://abc', 'name': 'link2'},
            {'url': 'http://abc', 'name': 'link4'},
            {'url': 'http://abc', 'name': 'link new'},
            ]}
        copy_across_resource_ids({'resources': [
            {'url': 'http://abc', 'name': 'link1', 'id': '1'},
            {'url': 'http://abc', 'name': 'link2', 'id': '2'},
            {'url': 'http://abc', 'name': 'link3', 'id': '3'},
            {'url': 'http://abc', 'name': 'link4', 'id': '4'},
            {'url': 'http://abc', 'name': 'link5', 'id': '5'},
            ]},
            harvested_dataset,
        )
        assert ([(r.get('id'), r['name']) for r in harvested_dataset['resources']] ==
            [('1', 'link1'), ('5', 'link5'), ('3', 'link3'), ('2', 'link2'),
             ('4', 'link4'), (None, 'link new')])

    def test_copied_with_keeping_existing_resources(self):
        existing_dataset = {'resources': [
            {'url': 'http://abc1', 'name': 'link 1', 'id': '1'},
            {'url': 'http://abc2', 'name': 'link 2', 'id': '2'},
            {'url': 'http://abc3', 'name': 'link 3', 'id': '3'},
            {'url': 'http://abc4', 'name': 'link 4', 'id': '4'},
            {'url': 'http://abc5', 'name': 'link 5', 'id': '5'},
            ]}
        harvested_dataset = {'resources': [
            {'url': 'http://abc1', 'name': 'link 1'},
            {'url': 'http://abc2', 'name': 'link 2'},
            {'url': 'http://abc3', 'name': 'link 3'},
            {'url': 'http://abc4', 'name': 'link 4'},
            {'url': 'http://abc00', 'name': 'new link'},
            ]}
        copy_across_resource_ids(
            existing_dataset=existing_dataset,
            harvested_dataset=harvested_dataset,
            config={'keep_existing_resources': True}
        )
        assert ([(r.get('id'), r['name']) for r in harvested_dataset['resources']] ==
            [('1', 'link 1'), ('2', 'link 2'), ('3', 'link 3'), ('4', 'link 4'),
             (None, 'new link'), ('5', 'link 5')])

    def test_not_copied_because_completely_different(self):
        harvested_dataset = {'resources': [
            {'url': 'http://def', 'name': 'link other'}]}
        copy_across_resource_ids({'resources': [
            {'url': 'http://abc', 'name': 'link', 'id': '1'}]},
            harvested_dataset,
        )
        assert harvested_dataset['resources'][0].get('id') == None
