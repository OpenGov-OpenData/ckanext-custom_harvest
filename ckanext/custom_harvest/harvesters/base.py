import os
import logging

import six
import requests
import rdflib

from ckan import plugins as p
from ckan import model

from ckantoolkit import config
import ckan.plugins.toolkit as toolkit

from ckanext.harvest.harvesters import HarvesterBase
from ckanext.harvest.model import HarvestObject

from ckan.lib.helpers import json
from ckanext.custom_harvest.configuration_processors import (
    DefaultTags, CleanTags,
    DefaultExtras, CopyExtras,
    DefaultGroups, DefaultValues,
    MappingFields, CompositeMapping,
    ContactPoint,
    RemoteGroups,
    OrganizationFilter,
    ResourceFormatOrder,
    KeepExistingResources,
    UploadToDatastore
)


log = logging.getLogger(__name__)


class CustomHarvester(HarvesterBase):
    force_import = False

    config = None
    config_processors = [
        DefaultTags,
        CleanTags,
        DefaultExtras,
        CopyExtras,
        DefaultGroups,
        DefaultValues,
        MappingFields,
        CompositeMapping,
        ContactPoint,
        RemoteGroups,
        OrganizationFilter,
        ResourceFormatOrder,
        KeepExistingResources,
        UploadToDatastore
    ]

    def _get_object_extra(self, harvest_object, key):
        '''
        Helper function for retrieving the value from a harvest object extra,
        given the key
        '''
        for extra in harvest_object.extras:
            if extra.key == key:
                return extra.value
        return None

    def get_original_url(self, harvest_object_id):
        obj = model.Session.query(HarvestObject). \
            filter(HarvestObject.id == harvest_object_id).\
            first()
        if obj:
            return obj.source.url
        return None

    def _read_datasets_from_db(self, guid):
        '''
        Returns a database result of datasets matching the given guid.
        '''

        datasets = model.Session.query(model.Package.id) \
                                .join(model.PackageExtra) \
                                .filter(model.PackageExtra.key == 'guid') \
                                .filter(model.PackageExtra.value == guid) \
                                .filter(model.Package.state == 'active') \
                                .all()
        return datasets

    def _get_existing_dataset(self, guid):
        '''
        Checks if a dataset with a certain guid extra already exists

        Returns a dict as the ones returned by package_show
        '''

        datasets = self._read_datasets_from_db(guid)

        if not datasets:
            return None
        elif len(datasets) > 1:
            log.error('Found more than one dataset with the same guid: {0}'
                      .format(guid))

        return p.toolkit.get_action('package_show')({'ignore_auth': True}, {'id': datasets[0][0]})

    # Start hooks

    def modify_package_dict(self, package_dict, source_dict, harvest_object):
        '''
            Allows custom harvesters to modify the package dict before
            creating or updating the actual package.
        '''

        try:
            self._set_config(harvest_object.job.source.config)
        except:
            self._set_config('')

        # Modify package_dict using config_processors
        for processor in self.config_processors:
            processor.modify_package_dict(package_dict, self.config, source_dict)

        return package_dict

    def _set_config(self, config_str):
        if config_str:
            self.config = json.loads(config_str)
            log.debug('Using config: %r', self.config)
        else:
            self.config = {}

    def validate_config(self, config):
        if not config:
            return config

        try:
            config_obj = json.loads(config)

            # Validate harvest config using config_processors
            # Processor validators can change config object (i.e. DefaultGroups)
            for processor in self.config_processors:
                processor.check_config(config_obj)

            config = json.dumps(config_obj, indent=4)
        except ValueError as e:
            raise e

        return config

    # End hooks