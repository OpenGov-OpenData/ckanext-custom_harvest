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
from ckan.lib.navl import dictization_functions
from ckanext.harvest.model import HarvestObject, HarvestObjectExtra
from ckanext.harvest.logic.schema import unicode_safe
from ckanext.custom_harvest import converter
from ckanext.custom_harvest import utils
from ckanext.custom_harvest.harvesters.base import CustomHarvester


log = logging.getLogger(__name__)

_validate = dictization_functions.validate


class PackageSearchHarvester(CustomHarvester):
    '''
    A Harvester for CKAN instances utilizing the package_search API
    '''

    def info(self):
        return {
            'name': 'package_search_harvest',
            'title': 'CKAN Package Search',
            'description': 'Harvester for CKAN instances utilizing the package_search API',
            'form_config_interface': 'Text'
        }

    def _get_content(self, url):
        headers = {}
        api_key = self.config.get('api_key')
        if api_key:
            headers['Authorization'] = api_key

        try:
            http_request = requests.get(url, headers=headers)
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
        log.debug('In PackageSearchHarvester gather_stage (%s)',
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

        # Get source URL
        parsed_url = urlparse(harvest_job.source.url)
        base_search_url = parsed_url.scheme + '://' + parsed_url.netloc

        query = ''
        fq_terms = []
        # Get package query
        query_string = harvest_job.source.url.split('/action/package_search?')[-1]
        if query_string:
            query_dict = parse_qs(query_string)
            schema = logic.schema.default_package_search_schema()
            valid_dict, errors = _validate(query_dict, schema, {})
            if errors:
                raise p.toolkit.ValidationError(errors)

            if query_dict.get('q'):
                query = ' '.join(query_dict.get('q'))
            if query_dict.get('fq'):
                fq_terms.append(' '.join(query_dict.get('fq')))

        # Filter in/out datasets from particular organizations
        org_filter_include = self.config.get('organizations_filter_include', [])
        org_filter_exclude = self.config.get('organizations_filter_exclude', [])
        if org_filter_include:
            fq_terms.append(' OR '.join(
                'organization:%s' % org_name for org_name in org_filter_include))
        elif org_filter_exclude:
            fq_terms.extend(
                '-organization:%s' % org_name for org_name in org_filter_exclude)

        # Request all remote packages
        try:
            pkg_dicts = self._search_for_datasets(base_search_url, query,
                                                    fq_terms)
            log.info('Found %s datasets at CKAN: %s',
                        len(pkg_dicts), base_search_url)
        except SearchError as e:
            log.info('Searching for all datasets gave an error: %s', e)
            self._save_gather_error(
                'Unable to search remote CKAN for datasets:%s url:%s'
                'terms:%s' % (e, base_search_url, fq_terms),
                harvest_job)
            return None
        if not pkg_dicts:
            self._save_gather_error(
                'No datasets found at CKAN: %s' % base_search_url,
                harvest_job)
            return []

        # Create harvest objects for each dataset
        try:
            guids_in_source = []
            for pkg_dict in pkg_dicts:
                guid = pkg_dict.get('name')
                log.info('Got identifier: {0}'.format(guid.encode('utf8')))
                guids_in_source.append(guid)
                log.info('Creating HarvestObject for %s %s', pkg_dict['name'], pkg_dict['id'])
                if guid in guids_in_db:
                    # Dataset needs to be updated
                    obj = HarvestObject(guid=guid, job=harvest_job,
                                        package_id=guid_to_package_id[guid],
                                        content=json.dumps(pkg_dict),
                                        extras=[
                                            HarvestObjectExtra(key='status', value='change'),
                                            HarvestObjectExtra(key='base_search_url', value=base_search_url)
                                        ])
                else:
                    # Dataset needs to be created
                    obj = HarvestObject(guid=guid, job=harvest_job,
                                        content=json.dumps(pkg_dict),
                                        extras=[
                                            HarvestObjectExtra(key='status', value='new'),
                                            HarvestObjectExtra(key='base_search_url', value=base_search_url)
                                        ])
                obj.save()
                ids.append(obj.id)

        except ValueError as e:
            msg = 'Error parsing file: {0}'.format(str(e))
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

    def _search_for_datasets(self, base_search_url, query=None, fq_terms=None):
        '''Does a dataset search on a remote CKAN and returns the results.

        Deals with paging to return all the results, not just the first page.
        '''
        base_search_url = base_search_url + '/api/action/package_search'
        params = {'rows': '100', 'start': '0'}

        params['sort'] = 'id asc'
        if query:
            params['q'] = query
        if fq_terms:
            params['fq'] = ' '.join(fq_terms)

        pkg_dicts = []
        pkg_ids = set()
        previous_content = None
        while True:
            url = base_search_url + '?' + urlencode(params)
            log.info('Searching for CKAN datasets: %s', url)
            try:
                content = self._get_content(url)
            except ContentFetchError as e:
                raise SearchError(
                    'Error sending request to search remote '
                    'CKAN instance %s using URL %r. Error: %s' %
                    (base_search_url, url, e))

            if previous_content and content == previous_content:
                raise SearchError('The paging doesn\'t seem to work. URL: %s' %
                                  url)
            try:
                response_dict = json.loads(content)
            except ValueError:
                raise SearchError('Response from remote CKAN was not JSON: %r'
                                  % content)
            try:
                pkg_dicts_page = response_dict.get('result', {}).get('results',
                                                                     [])
            except ValueError:
                raise SearchError('Response JSON did not contain '
                                  'result/results: %r' % response_dict)

            # Weed out any datasets found on previous pages (should datasets be
            # changing while we page)
            ids_in_page = set(p['id'] for p in pkg_dicts_page)
            duplicate_ids = ids_in_page & pkg_ids
            if duplicate_ids:
                pkg_dicts_page = [p for p in pkg_dicts_page
                                  if p['id'] not in duplicate_ids]
            pkg_ids |= ids_in_page

            pkg_dicts.extend(pkg_dicts_page)

            if len(pkg_dicts_page) == 0:
                break

            params['start'] = str(int(params['start']) + int(params['rows']))

        return pkg_dicts

    def fetch_stage(self, harvest_object):
        # Nothing to do here - we got the package dict in the search in the
        # gather stage
        return True

    def import_stage(self, harvest_object):
        log.debug('In PackageSearchHarvester import_stage')

        context = {'model': model, 'session': model.Session,
                   'user': self._get_user_name()}
        if not harvest_object:
            log.error('No harvest object received')
            return False

        base_search_url = self._get_object_extra(harvest_object, 'base_search_url')
        status = self._get_object_extra(harvest_object, 'status')
        if status == 'delete':
            # Delete package
            p.toolkit.get_action('package_delete')(context, {'id': harvest_object.package_id})
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

        source_dict = json.loads(harvest_object.content)
        package_dict = converter.package_search_to_ckan(source_dict)

        if source_dict.get('type') != 'dataset':
            log.warning('Remote dataset is not a dataset, ignoring...')
            return True

        try:
            # copy across ids from the existing dataset, otherwise they'll
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
                package_dict['name'] = self._gen_new_name(source_dict.get('name'))

            package_dict = self.modify_package_dict(package_dict, source_dict, harvest_object)

            # Get owner organization from the harvest source dataset
            harvest_source_dataset = model.Package.get(harvest_object.source.id)
            if harvest_source_dataset.owner_org:
                package_dict['owner_org'] = harvest_source_dataset.owner_org

            # Flag this object as the current one
            harvest_object.current = True
            harvest_object.add()

            context = {
                'user': self._get_user_name(),
                'return_id_only': True,
                'ignore_auth': True,
            }

            if status == 'new':
                package_schema = logic.schema.default_create_package_schema()
                context['schema'] = package_schema

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

                package_id = p.toolkit.get_action(action)(context, package_dict)
                log.info('%s dataset with id %s', message_status, package_id)

                # Upload tabular resources to datastore
                upload_to_datastore = self.config.get('upload_to_datastore', True)
                if upload_to_datastore and p.get_plugin('xloader'):
                    # Get package dict again in case there's new resource ids
                    pkg_dict = p.toolkit.get_action('package_show')(context, {'id': package_id})
                    upload_resources_to_datastore(context, pkg_dict, source_dict, base_search_url)
        except Exception as e:
            dataset = json.loads(harvest_object.content)
            dataset_name = dataset.get('name', '')

            self._save_object_error('Error importing dataset %s: %r / %s' % (dataset_name, e, traceback.format_exc()), harvest_object, 'Import')
            return False

        finally:
            model.Session.commit()

        return True


def copy_across_resource_ids(existing_dataset, harvested_dataset, config=None):
    '''Compare the resources in a dataset existing in the CKAN database with
    the resources in a freshly harvested copy, and for any resources that are
    the same, copy the resource ID into the harvested_dataset dict.
    '''
    # take a copy of the existing_resources so we can remove them when they are
    # matched - we don't want to match them more than once.
    existing_resources_still_to_match = \
        [r for r in existing_dataset.get('resources')]

    # we match resources a number of ways. we'll compute an 'identity' of a
    # resource in both datasets and see if they match.
    # start with the surest way of identifying a resource, before reverting
    # to closest matches.
    resource_identity_functions = [
        lambda r: (r['url'], r['name'], r['format'], r['position']),
        lambda r: (r['url'], r['name'], r['format']),
        lambda r: (r['url'], r['name']),
        lambda r: r['url'],  # same URL is fine if nothing else matches
    ]

    datastore_fields = [
        'datastore_active',
        'datastore_contains_all_records_of_source_file'
    ]

    for resource_identity_function in resource_identity_functions:
        # calculate the identities of the existing_resources
        existing_resource_identities = {}
        for r in existing_resources_still_to_match:
            try:
                identity = resource_identity_function(r)
                existing_resource_identities[identity] = r
            except KeyError:
                pass

        # calculate the identities of the harvested_resources
        for resource in harvested_dataset.get('resources'):
            try:
                identity = resource_identity_function(resource)
            except KeyError:
                identity = None
            if identity and identity in existing_resource_identities:
                # we got a match with the existing_resources - copy the id
                matching_existing_resource = \
                    existing_resource_identities[identity]
                resource['id'] = matching_existing_resource['id']
                # copy datastore specific fields
                for field in datastore_fields:
                    if matching_existing_resource.get(field):
                        resource[field] = matching_existing_resource.get(field)
                # make sure we don't match this existing_resource again
                del existing_resource_identities[identity]
                existing_resources_still_to_match.remove(
                    matching_existing_resource)
        if not existing_resources_still_to_match:
            break

    # If configured add rest of existing resources to harvested dataset
    try:
        keep_existing_resources = config.get('keep_existing_resources', False)
        if keep_existing_resources and harvested_dataset.get('resources'):
            for existing_resource in existing_resources_still_to_match:
                if existing_resource.get('url'):
                    harvested_dataset['resources'].append(existing_resource)
    except Exception:
        pass


def upload_resources_to_datastore(context, package_dict, source_dict, base_search_url):
    for resource in package_dict.get('resources'):
        if utils.is_xloader_format(resource.get('format')) and resource.get('id'):
            # Get data dictionary if available and push to datastore
            push_data_dictionary(context, resource, source_dict, base_search_url)

            # Submit the resource to be pushed to the datastore
            try:
                log.info('Submitting harvested resource {0} to be xloadered'.format(resource.get('id')))
                xloader_dict = {
                    'resource_id': resource.get('id'),
                    'ignore_hash': False
                }
                p.toolkit.get_action('xloader_submit')(context, xloader_dict)
            except p.toolkit.ValidationError as e:
                log.debug(e)
                pass


def push_data_dictionary(context, resource, source_dict, base_search_url):
    # Check for resource's data dictionary
    fields = []
    for source_resource in source_dict.get('resources'):
        if (resource.get('url') == source_resource.get('url') and
                resource.get('title') == source_resource.get('name') and
                source_resource.get('datastore_active')):
            try:
                query_url = base_search_url + '/api/action/datastore_search?limit=0&resource_id=' + source_resource.get('id')
                datastore_response = requests.get(query_url, timeout=30)
                data = datastore_response.json()
                result = data.get('result', {})
                fields = result.get('fields', [])
                if len(fields) > 0 and fields[0].get('id') == '_id':
                    del fields[0]  # Remove the first dictionary which is only for ckan row number
                break
            except Exception as e:
                log.debug(e)
                pass
    # If fields are defined push the data dictionary to datastore
    if fields:
        log.info('Pushing data dictionary for resource '.format(resource.get('id')))
        try:
            datastore_dict = {
                'resource_id': resource.get('id'),
                'fields': fields,
                'force': True
            }
            p.toolkit.get_action('datastore_create')(context, datastore_dict)
        except Exception as e:
            log.debug(e)
            pass

class ContentFetchError(Exception):
    pass


class SearchError(Exception):
    pass
