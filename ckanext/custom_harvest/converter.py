import logging
import mimetypes
from ckan.common import config
from ckan.plugins import toolkit


log = logging.getLogger(__name__)
mimetypes.init()


def package_search_to_ckan(source_dict):
    package_dict = {}

    package_dict['title'] = source_dict.get('title')
    package_dict['notes'] = source_dict.get('notes', '')

    if 'fluent' in config.get('ckan.plugins'):
        package_dict['title_translated'] = {'en': source_dict.get('title')}
        package_dict['notes_translated'] = {'en': source_dict.get('notes', '') or ''}
    
    package_dict['tags'] = []
    for tag in source_dict.get('tags', []):
        if tag.get('name'):
            package_dict['tags'].append({'name': tag.get('name')})
    
    package_dict['extras'] = []
    package_dict['extras'].append({'key': 'guid', 'value': source_dict.get('name')})

    for extra in source_dict.get('extras', []):
        if extra.get('key') == 'spatial' and extra.get('value'):
            package_dict['extras'].append({'key': extra.get('key'), 'value': extra.get('value')})
    
    if source_dict.get('license'):
        for license in toolkit.get_action('license_list')({}, {}):
            if license.get('url') == source_dict.get('license'):
                package_dict['license_id'] = license.get('id')
                break
            elif license.get('title') == source_dict.get('license'):
                package_dict['license_id'] = license.get('id')
                break

    package_dict['resources'] = []
    for resource in source_dict.get('resources', []):
        # Guess format if not present
        format = ''
        if resource.get('format'):
            format = resource.get('format')
        elif resource.get('mediaType'):
            ext = mimetypes.guess_extension(resource.get('mediaType'))
            if ext:
                format = ext[1:]

        # skip disallowed formats
        clean_format = ''.join(format.split()).lower()
        if disallow_file_format(clean_format):
            log.debug('Skip disallowed format %s: %s' % (
                format, resource.get('url'))
            )
            continue

        resource = {
            'name': resource.get('title', source_dict.get('title')),
            'description': resource.get('description', ''),
            'url': resource.get('url'),
            'format': format,
        }

        if 'fluent' in config.get('ckan.plugins'):
            resource['name_translated'] = {'en': resource.get('title', source_dict.get('title'))}
            resource['description_translated'] = {'en': resource.get('description', '') or ''}

        if resource.get('size'):
            try:
                resource['size'] = int(resource.get('size'))
            except ValueError:
                pass
        package_dict['resources'].append(resource)

    return package_dict


def disallow_file_format(file_format):
    if config.get('ckanext.format_filter.filter_type') == 'whitelist':
        if file_format in get_whitelist():
            return False
        return True
    elif config.get('ckanext.format_filter.filter_type') == 'blacklist':
        if file_format in get_blacklist():
            return True
    return False


def get_whitelist():
    whitelist_string = config.get('ckanext.format_filter.whitelist', '')
    return convert_to_filter_list(whitelist_string)


def get_blacklist():
    blacklist_string = config.get('ckanext.format_filter.blacklist', '')
    return convert_to_filter_list(blacklist_string)


def convert_to_filter_list(filter_string):
    format_list = []
    try:
        if filter_string:
            if isinstance(filter_string, str):
                filter_string = filter_string.split()
                format_list = [file_format.lower() for file_format in filter_string]
    except Exception as e:
        log.error(e)
    return format_list
