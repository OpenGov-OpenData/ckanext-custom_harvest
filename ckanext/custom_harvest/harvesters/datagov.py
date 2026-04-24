import uuid
import logging
import requests
import traceback
from requests.exceptions import HTTPError, RequestException
from urllib.parse import urlencode, urlparse, parse_qs

from ckan import model
from ckan import logic
from ckan import plugins as p
from ckan.lib.helpers import json
from ckanext.harvest.model import HarvestObject, HarvestObjectExtra
from ckanext.harvest.logic.schema import unicode_safe
from ckanext.custom_harvest import converter
from ckanext.custom_harvest.harvesters.base import CustomHarvester
from ckanext.custom_harvest.harvesters.package_search import (
    copy_across_resource_ids,
    upload_resources_to_datastore
)


log = logging.getLogger(__name__)


class DataGovHarvester(CustomHarvester):
    '''
    A Harvester for Data.gov catalog using the Search API
    '''

    def info(self):
        return {
            'name': 'datagov_harvest',
            'title': 'Data.gov Harvester',
            'description': 'Harvester for Data.gov using their Catalog API',
            'form_config_interface': 'Text'
        }

    def _get_content(self, url):
        headers = {}
        api_key = self.config.get('api_key')
        if api_key:
            headers['Authorization'] = api_key

        try:
            http_request = requests.get(url, headers=headers, timeout=30)
            http_request.raise_for_status()
        except HTTPError as e:
            raise ContentFetchError('HTTP error: %s %s' % (e.response.status_code, e.request.url))
        except RequestException as e:
            raise ContentFetchError('Request error: %s' % e)
        except Exception as e:
            raise ContentFetchError('HTTP general exception: %s' % e)
        return http_request.text

    def _set_config(self, config_str):
        if config_str:
            self.config = json.loads(config_str)
            log.debug('Using config: %r', self.config)
        else:
            self.config = {}

    def gather_stage(self, harvest_job):
        log.debug('In DataGovHarvester gather_stage (%s)',
                  harvest_job.source.url)

        ids = []

        # Get the previous guids for this source
        query = \
            model.Session.query(HarvestObject.guid, HarvestObject.package_id) \
            .filter(HarvestObject.current == True) \
            .filter(HarvestObject.harvest_source_id == harvest_job.source.id)
        guid_to_package_id = {}

        for guid, package_id in query:
            guid_to_package_id[guid] = package_id

        guids_in_db = list(guid_to_package_id.keys())
        guids_in_source = []

        self._set_config(harvest_job.source.config)

        # Parse source URL
        parsed_url = urlparse(harvest_job.source.url)
        base_search_url = parsed_url.scheme + '://' + parsed_url.netloc + parsed_url.path

        # Extract ALL query parameters from URL to preserve them during pagination
        url_params = {}
        if parsed_url.query:
            query_dict = parse_qs(parsed_url.query)
            # Convert parse_qs result (dict of lists) to dict of single values
            for key, value_list in query_dict.items():
                if len(value_list) == 1:
                    url_params[key] = value_list[0]
                else:
                    # Join multiple values with space
                    url_params[key] = ' '.join(value_list)

        # Request all remote datasets
        try:
            dataset_dicts = self._search_for_datasets(
                base_search_url,
                url_params
            )
            log.info('Found %s datasets at Data.gov: %s',
                        len(dataset_dicts), base_search_url)
        except SearchError as e:
            log.info('Searching for all datasets gave an error: %s', e)
            self._save_gather_error(
                'Unable to search Data.gov for datasets: %s url: %s '
                'params: %s' % (e, base_search_url, url_params),
                harvest_job)
            return None
        if not dataset_dicts:
            self._save_gather_error(
                'No datasets found at Data.gov: %s' % base_search_url,
                harvest_job)
            return []

        # Filter datasets by organization if configured
        org_filter_include = self.config.get('organizations_filter_include', [])
        org_filter_exclude = self.config.get('organizations_filter_exclude', [])

        if org_filter_include or org_filter_exclude:
            filtered_datasets = []
            for dataset_dict in dataset_dicts:
                org_slug = dataset_dict.get('organization', {}).get('slug', '')

                # Apply include filter
                if org_filter_include:
                    if org_slug in org_filter_include:
                        filtered_datasets.append(dataset_dict)
                    else:
                        log.debug('Excluding dataset %s - org %s not in include list',
                                  dataset_dict.get('identifier'), org_slug)
                # Apply exclude filter
                elif org_filter_exclude:
                    if org_slug not in org_filter_exclude:
                        filtered_datasets.append(dataset_dict)
                    else:
                        log.debug('Excluding dataset %s - org %s in exclude list',
                                  dataset_dict.get('identifier'), org_slug)

            log.info('Filtered %s datasets to %s based on organization filters',
                     len(dataset_dicts), len(filtered_datasets))
            dataset_dicts = filtered_datasets

        if not dataset_dicts:
            log.info('No datasets remaining after organization filtering')
            return []

        # Create harvest objects for each dataset
        try:
            guids_in_source = []
            for dataset_dict in dataset_dicts:
                guid = dataset_dict.get('identifier')

                if not guid:
                    log.warning('Dataset missing identifier: %s', dataset_dict.get('title'))
                    continue

                log.info('Got identifier: {0}'.format(guid))
                guids_in_source.append(guid)
                log.info('Creating HarvestObject for %s', guid)

                if guid in guids_in_db:
                    # Dataset needs to be updated
                    obj = HarvestObject(guid=guid, job=harvest_job,
                                        package_id=guid_to_package_id[guid],
                                        content=json.dumps(dataset_dict),
                                        extras=[
                                            HarvestObjectExtra(key='status', value='change'),
                                            HarvestObjectExtra(key='base_search_url', value=base_search_url)
                                        ])
                else:
                    # Dataset needs to be created
                    obj = HarvestObject(guid=guid, job=harvest_job,
                                        content=json.dumps(dataset_dict),
                                        extras=[
                                            HarvestObjectExtra(key='status', value='new'),
                                            HarvestObjectExtra(key='base_search_url', value=base_search_url)
                                        ])
                obj.save()
                ids.append(obj.id)

        except ValueError as e:
            msg = 'Error parsing dataset: {0}'.format(str(e))
            self._save_gather_error(msg, harvest_job)
            return None

        # Check datasets that need to be deleted
        guids_to_delete = set(guids_in_db) - set(guids_in_source)
        for guid in guids_to_delete:
            obj = HarvestObject(
                guid=guid, job=harvest_job,
                package_id=guid_to_package_id[guid],
                extras=[HarvestObjectExtra(key='status', value='delete')])
            ids.append(obj.id)
            model.Session.query(HarvestObject).\
                filter_by(guid=guid).\
                update({'current': False}, False)
            obj.save()

            # Rename package before delete so that its url can be reused
            context = {'model': model, 'session': model.Session,
                       'user': self._get_user_name()}
            p.toolkit.get_action('package_patch')(context, {
                'id': guid_to_package_id[guid],
                'name': guid_to_package_id[guid] + '-deleted'
            })

        return ids

    def _search_for_datasets(self, base_search_url, url_params=None):
        '''
        Performs dataset search on Data.gov with cursor-based pagination.
        Returns all results across all pages.

        Args:
            base_search_url: Base URL for the search endpoint
            url_params: Dictionary of query parameters from the source URL
        '''
        # Start with URL params (preserves all original query parameters)
        params = dict(url_params) if url_params else {}

        # Per page setting from config or default to 100
        per_page = self.config.get('per_page', 100)
        params['per_page'] = str(per_page)

        # Add other params from config (these override URL params if present)
        if self.config.get('sort'):
            params['sort'] = self.config.get('sort')
        if self.config.get('org_slug'):
            params['org_slug'] = self.config.get('org_slug')

        datasets = []
        after_cursor = None
        page_num = 0

        while True:
            page_num += 1
            if after_cursor:
                params['after'] = after_cursor

            url = base_search_url + '?' + urlencode(params)
            log.info('Fetching Data.gov page %s: %s', page_num, url)

            try:
                content = self._get_content(url)
            except ContentFetchError as e:
                raise SearchError(
                    'Error sending request to search Data.gov '
                    'instance %s using URL %r. Error: %s' %
                    (base_search_url, url, e))

            try:
                response_dict = json.loads(content)
            except ValueError:
                raise SearchError('Response from Data.gov was not JSON: %r'
                                  % content)

            # Data.gov returns results directly (not wrapped in 'result')
            results = response_dict.get('results', [])

            if not isinstance(results, list):
                raise SearchError('Response JSON did not contain '
                                  'results array: %r' % response_dict)

            datasets.extend(results)
            log.info('Page %s: Got %s datasets (total so far: %s)',
                     page_num, len(results), len(datasets))

            # Check for next page cursor
            after_cursor = response_dict.get('after')
            if not after_cursor:
                log.info('No more pages. Total datasets: %s', len(datasets))
                break

            # Safety check to prevent infinite loops
            if page_num > 1000:
                log.warning('Reached maximum page limit (1000). Stopping pagination.')
                break

        return datasets

    def fetch_stage(self, harvest_object):
        # Nothing to do here - we got the dataset in the search in the
        # gather stage
        return True

    def import_stage(self, harvest_object):
        log.debug('In DataGovHarvester import_stage')

        if not harvest_object:
            log.error('No harvest object received')
            return False

        base_search_url = self._get_object_extra(harvest_object, 'base_search_url')
        status = self._get_object_extra(harvest_object, 'status')

        if status == 'delete':
            # Delete package
            delete_context = {
                'model': model,
                'session': model.Session,
                'user': self._get_user_name()
            }
            p.toolkit.get_action('package_delete')(delete_context, {'id': harvest_object.package_id})
            log.info('Deleted package {0} with guid {1}'
                     .format(harvest_object.package_id, harvest_object.guid))

            return True

        if harvest_object.content is None:
            self._save_object_error('Empty content for object %s' %
                                    harvest_object.id,
                                    harvest_object, 'Import')
            return False

        # Get the last harvested object (if any)
        previous_object = model.Session.query(HarvestObject) \
            .filter(HarvestObject.guid == harvest_object.guid) \
            .filter(HarvestObject.current == True) \
            .first()

        # Flag previous object as not current anymore
        if previous_object and not self.force_import:
            previous_object.current = False
            previous_object.add()

        self._set_config(harvest_object.job.source.config)

        # Convert Data.gov format to CKAN format
        source_dict = json.loads(harvest_object.content)
        package_dict = converter.datagov_to_ckan(source_dict)

        try:
            # Copy across ids from the existing dataset, otherwise they'll
            # be recreated with new ids
            if status == 'change':
                existing_dataset = self._get_existing_dataset(harvest_object.guid)
                if existing_dataset:
                    copy_across_resource_ids(existing_dataset, package_dict, self.config)
                    package_dict['name'] = existing_dataset.get('name')
                    # Copy across private status
                    if 'private' in existing_dataset.keys():
                        package_dict['private'] = existing_dataset['private']

            # Set name for new package to prevent name conflict
            if not package_dict.get('name'):
                # Use slug if available, otherwise use identifier
                name = source_dict.get('slug') or harvest_object.guid
                package_dict['name'] = self._gen_new_name(name)

            # Ensure source_dict has fields expected by config processors
            # Copy groups from package_dict (which were mapped from themes) to source_dict
            # so that RemoteGroups processor can validate them
            source_dict['groups'] = package_dict.get('groups', [])

            # Copy extras from package_dict to source_dict so CompositeMapping and other
            # processors can reference converted fields (e.g., extras.dcat_modified)
            if 'extras' not in source_dict:
                source_dict['extras'] = []
            source_dict['extras'].extend(package_dict.get('extras', []))

            # Apply config processors
            package_dict = self.modify_package_dict(package_dict, source_dict, harvest_object)

            # Get owner organization from the harvest source dataset
            harvest_source_dataset = model.Package.get(harvest_object.source.id)
            if harvest_source_dataset.owner_org:
                package_dict['owner_org'] = harvest_source_dataset.owner_org

            # Flag this object as the current one
            harvest_object.current = True
            harvest_object.add()

            # Context for package create/update
            package_context = {
                'user': self._get_user_name(),
                'return_id_only': True,
                'ignore_auth': True,
            }

            if status == 'new':
                package_schema = logic.schema.default_create_package_schema()
                package_context['schema'] = package_schema

                # We need to explicitly provide a package ID
                package_dict['id'] = str(uuid.uuid4())
                package_schema['id'] = [unicode_safe]

                # Save reference to the package on the object
                harvest_object.package_id = package_dict['id']
                harvest_object.add()

                # Defer constraints and flush so the dataset can be indexed with
                # the harvest object id (on the after_show hook from the harvester
                # plugin)
                model.Session.execute(
                    'SET CONSTRAINTS harvest_object_package_id_fkey DEFERRED')
                model.Session.flush()

            elif status == 'change':
                package_dict['id'] = harvest_object.package_id

            if status in ['new', 'change']:
                action = 'package_create' if status == 'new' else 'package_update'
                message_status = 'Created' if status == 'new' else 'Updated'

                package_id = p.toolkit.get_action(action)(package_context, package_dict)
                log.info('%s dataset with id %s', message_status, package_id)

                # Upload tabular resources to datastore
                upload_to_datastore = self.config.get('upload_to_datastore', True)
                if upload_to_datastore and p.plugin_loaded('xloader'):
                    # Get package dict again in case there's new resource ids
                    pkg_dict = p.toolkit.get_action('package_show')(package_context, {'id': package_id})
                    upload_resources_to_datastore(package_context, pkg_dict, source_dict, base_search_url)

        except Exception as e:
            dataset_name = source_dict.get('slug') or source_dict.get('identifier', '')

            self._save_object_error('Error importing dataset %s: %r / %s' % (dataset_name, e, traceback.format_exc()), harvest_object, 'Import')
            return False

        finally:
            model.Session.commit()

        return True


class ContentFetchError(Exception):
    pass


class SearchError(Exception):
    pass
