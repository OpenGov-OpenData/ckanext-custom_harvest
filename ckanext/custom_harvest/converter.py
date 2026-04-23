import logging
import mimetypes
import re
from urllib.parse import urlparse
from ckan.common import config
from ckan.plugins import toolkit
from ckan.lib.helpers import json


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

    for key in ['metadata_created', 'metadata_modified']:
        package_dict['extras'].append({'key': 'source_{0}'.format(key), 'value': source_dict.get(key)})

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
    for source_resource in source_dict.get('resources', []):
        # Guess format if not present
        format = ''
        if source_resource.get('format'):
            format = source_resource.get('format')
        elif source_resource.get('mimetype'):
            ext = mimetypes.guess_extension(source_resource.get('mimetype'))
            if ext:
                format = ext[1:]

        # skip disallowed formats
        clean_format = ''.join(format.split()).lower()
        if disallow_file_format(clean_format):
            log.debug('Skip disallowed format %s: %s' % (
                format, source_resource.get('url'))
            )
            continue

        resource = {
            'name': source_resource.get('name'),
            'description': source_resource.get('description', ''),
            'url': source_resource.get('url'),
            'format': format,
        }

        if 'fluent' in config.get('ckan.plugins'):
            resource['name_translated'] = {'en': source_resource.get('name')}
            resource['description_translated'] = {'en': source_resource.get('description', '') or ''}

        if int(source_resource.get('position')) >= 0:
            resource['position'] = int(source_resource.get('position'))

        if source_resource.get('size'):
            try:
                resource['size'] = int(source_resource.get('size'))
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


def datagov_to_ckan(source_dict):
    '''
    Converts a Data.gov Search API result to CKAN package dict format.

    Maps both top-level fields and nested DCAT-US metadata.
    '''
    package_dict = {}

    # Basic metadata from top-level fields
    package_dict['title'] = source_dict.get('title', 'Untitled Dataset')
    package_dict['notes'] = source_dict.get('description', '')

    # Fluent support (if enabled)
    if 'fluent' in config.get('ckan.plugins'):
        package_dict['title_translated'] = {'en': source_dict.get('title', 'Untitled Dataset')}
        package_dict['notes_translated'] = {'en': source_dict.get('description', '') or ''}

    # Tags from keywords
    package_dict['tags'] = []
    for keyword in source_dict.get('keyword', []):
        if keyword:
            munged_tag = munge_tag(keyword)
            if munged_tag:
                package_dict['tags'].append({'name': munged_tag})

    # Groups - Map Data.gov themes to CKAN groups
    package_dict['groups'] = []

    # Get themes from both top-level and dcat fields
    themes = set()
    if source_dict.get('theme'):
        themes.update(source_dict.get('theme'))

    dcat = source_dict.get('dcat', {})
    if dcat.get('theme'):
        themes.update(dcat.get('theme'))

    # Convert themes to group format with slugified names
    for theme in themes:
        if theme:
            # Create a slug-friendly name from the theme
            group_name = munge_tag(theme.lower().replace(' ', '-'))
            if group_name:
                package_dict['groups'].append({'name': group_name})

    # Extras - store comprehensive metadata
    package_dict['extras'] = []

    # Core identifiers
    package_dict['extras'].append({
        'key': 'guid',
        'value': source_dict.get('identifier')
    })
    if source_dict.get('slug'):
        package_dict['extras'].append({
            'key': 'datagov_slug',
            'value': source_dict.get('slug')
        })

    # Temporal information
    if source_dict.get('last_harvested_date'):
        package_dict['extras'].append({
            'key': 'source_metadata_modified',
            'value': trim_date(source_dict.get('last_harvested_date'))
        })

    # Organization/Publisher
    if source_dict.get('publisher'):
        package_dict['extras'].append({
            'key': 'publisher',
            'value': source_dict.get('publisher')
        })

    org = source_dict.get('organization', {})
    if org:
        if org.get('name'):
            package_dict['extras'].append({
                'key': 'source_organization_name',
                'value': org.get('name')
            })
        if org.get('organization_type'):
            package_dict['extras'].append({
                'key': 'source_organization_type',
                'value': org.get('organization_type')
            })

    # Spatial information
    if source_dict.get('has_spatial'):
        package_dict['extras'].append({
            'key': 'has_spatial',
            'value': str(source_dict.get('has_spatial'))
        })

    # DCAT-US metadata (core fields)
    dcat = source_dict.get('dcat', {})
    if dcat:
        # Access level
        if dcat.get('accessLevel'):
            package_dict['extras'].append({
                'key': 'dcat_access_level',
                'value': dcat.get('accessLevel')
            })

        # Modified date
        if dcat.get('modified'):
            package_dict['extras'].append({
                'key': 'dcat_modified',
                'value': trim_date(dcat.get('modified'))
            })

        # Contact point
        contact_point = dcat.get('contactPoint', {})
        if contact_point:
            if contact_point.get('fn'):
                package_dict['extras'].append({
                    'key': 'contact_name',
                    'value': contact_point.get('fn')
                })
            if contact_point.get('hasEmail'):
                email = contact_point.get('hasEmail', '').replace('mailto:', '')
                package_dict['extras'].append({
                    'key': 'contact_email',
                    'value': email
                })

        # License
        if dcat.get('license'):
            license_id = map_datagov_license(dcat.get('license'))
            if license_id:
                package_dict['license_id'] = license_id

        # Spatial (GeoJSON) - prefer spatial_shape over dcat.spatial
        # spatial_shape is a proper GeoJSON polygon, dcat.spatial is just a bbox string
        spatial_value = None

        # First try spatial_shape from top-level (GeoJSON polygon)
        if source_dict.get('spatial_shape'):
            spatial_value = source_dict.get('spatial_shape')
            if isinstance(spatial_value, dict):
                spatial_value = json.dumps(spatial_value)
        # Fall back to dcat.spatial (bounding box string)
        elif dcat.get('spatial'):
            spatial_value = dcat.get('spatial')
            if isinstance(spatial_value, dict):
                spatial_value = json.dumps(spatial_value)

        if spatial_value:
            package_dict['extras'].append({
                'key': 'spatial',
                'value': spatial_value
            })

        # Spatial centroid (for map display/search)
        if source_dict.get('spatial_centroid'):
            centroid = source_dict.get('spatial_centroid')
            if isinstance(centroid, dict):
                # Store as "lat,lon" string for compatibility
                lat = centroid.get('lat')
                lon = centroid.get('lon')
                if lat is not None and lon is not None:
                    package_dict['extras'].append({
                        'key': 'spatial_centroid',
                        'value': '{},{}'.format(lat, lon)
                    })

        # Temporal
        if dcat.get('temporal'):
            package_dict['extras'].append({
                'key': 'temporal',
                'value': dcat.get('temporal')
            })

        # Landing page
        if dcat.get('landingPage'):
            package_dict['extras'].append({
                'key': 'landing_page',
                'value': dcat.get('landingPage')
            })

    # Resources/Distributions
    package_dict['resources'] = []
    distributions = dcat.get('distribution', []) if dcat else []

    for idx, dist in enumerate(distributions):
        # Skip if no access URL
        if not dist.get('accessURL') and not dist.get('downloadURL'):
            continue

        # Prefer downloadURL over accessURL
        resource_url = dist.get('downloadURL') or dist.get('accessURL')

        resource = {
            'name': dist.get('title', '') or dist.get('description', '') or 'Distribution {}'.format(idx + 1),
            'description': dist.get('description', ''),
            'url': resource_url,
            'format': extract_format(dist),
        }

        # Fluent support
        if 'fluent' in config.get('ckan.plugins'):
            resource['name_translated'] = {'en': resource['name']}
            resource['description_translated'] = {'en': resource['description'] or ''}

        # Media type
        if dist.get('mediaType'):
            resource['mimetype'] = dist.get('mediaType')

        # Size
        if dist.get('byteSize'):
            try:
                resource['size'] = int(dist.get('byteSize'))
            except (ValueError, TypeError):
                pass

        # Position for ordering
        resource['position'] = idx

        # Skip disallowed formats
        clean_format = ''.join(resource['format'].split()).lower()
        if disallow_file_format(clean_format):
            log.debug('Skip disallowed format %s: %s', resource['format'], resource['url'])
            continue

        package_dict['resources'].append(resource)

    return package_dict


def extract_format(distribution):
    '''Extract format from distribution metadata'''
    # Try format field first
    if distribution.get('format'):
        return distribution.get('format')

    # Try to extract from mediaType
    if distribution.get('mediaType'):
        mimetype = distribution.get('mediaType')
        ext = mimetypes.guess_extension(mimetype)
        if ext:
            return ext[1:].upper()  # Remove leading dot and uppercase

    # Try to extract from URL
    url = distribution.get('downloadURL') or distribution.get('accessURL', '')
    if url:
        # Check URL extension
        parsed = urlparse(url)
        path = parsed.path
        if '.' in path:
            ext = path.split('.')[-1].lower()
            # Common data formats
            if ext in ['csv', 'json', 'xml', 'pdf', 'xlsx', 'xls', 'zip',
                       'geojson', 'shp', 'kml', 'kmz', 'txt', 'html']:
                return ext.upper()

    return ''


def map_datagov_license(license_url):
    '''
    Maps license URLs to CKAN license IDs.
    Returns None if no match found.
    '''
    # Common license mappings
    license_mappings = {
        'http://www.opendefinition.org/licenses/cc-zero': 'cc-zero',
        'https://creativecommons.org/publicdomain/zero/1.0/': 'cc-zero',
        'http://creativecommons.org/publicdomain/zero/1.0/': 'cc-zero',
        'http://www.opendefinition.org/licenses/cc-by': 'cc-by',
        'https://creativecommons.org/licenses/by/4.0/': 'cc-by',
        'http://creativecommons.org/licenses/by/4.0/': 'cc-by',
        'http://www.opendefinition.org/licenses/odc-pddl': 'odc-pddl',
        'http://opendatacommons.org/licenses/pddl/': 'odc-pddl',
    }

    if license_url in license_mappings:
        return license_mappings[license_url]

    # Try to match against CKAN's license list
    try:
        for license in toolkit.get_action('license_list')({}, {}):
            if license.get('url') == license_url:
                return license.get('id')
            elif license.get('title') == license_url:
                return license.get('id')
    except Exception:
        pass

    return None


def munge_tag(tag):
    '''Sanitize tag string for CKAN'''
    from ckan.lib.munge import substitute_ascii_equivalents

    tag = substitute_ascii_equivalents(tag)
    tag = tag.strip()
    # Remove invalid characters
    tag = re.sub(r'[^a-zA-Z0-9 \-_.]', '', tag)
    tag = tag.strip()

    # Truncate to max length
    if len(tag) > 100:
        tag = tag[:100]

    return tag


def trim_date(date_string):
    '''
    Trim ISO 8601 timestamp to date if time is midnight.

    Examples:
        '2015-10-02T00:00:00.000+00:00' -> '2015-10-02'
        '2015-10-02T14:30:00.000+00:00' -> '2015-10-02T14:30:00.000+00:00' (kept)
        '2015-10-02' -> '2015-10-02' (no change)
    '''
    if not date_string or not isinstance(date_string, str):
        return date_string

    # Check if it looks like an ISO timestamp with time
    if 'T' in date_string:
        # Check if time is midnight (00:00:00)
        if re.match(r'.*T00:00:00(\.\d+)?(Z|[+-]\d{2}:\d{2})?$', date_string):
            # Extract just the date part
            return date_string.split('T')[0]

    return date_string
