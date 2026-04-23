# Data.gov Harvester

This document describes the Data.gov harvester implementation for CKAN.

## Overview

The Data.gov harvester (`DataGovHarvester`) enables CKAN to harvest datasets from Data.gov's catalog using their current Search API. This replaces the legacy CKAN-based API with support for Data.gov's new API endpoint and DCAT-US metadata format.

## Features

- **Cursor-based pagination**: Efficiently handles large result sets using Data.gov's `after` cursor
- **DCAT-US metadata mapping**: Maps Data.gov's DCAT-US metadata format to CKAN's internal structure
- **Configurable query parameters**: Supports all Data.gov API parameters including `q`, `keyword`, `org_slug`, `spatial_geometry`, and more
- **Resource tracking**: Preserves resource IDs across harvests to maintain datastore data
- **Comprehensive metadata**: Maps core DCAT-US fields including spatial, temporal, contact points, and more
- **Extensible configuration**: Supports all configuration processors from CustomHarvester base class

## Installation

1. Add the harvester plugin to your CKAN config:

```ini
ckan.plugins = ... custom_harvest datagov_harvester
```

2. Restart CKAN

## Creating a Harvest Source

1. Navigate to Organizations → [Your Organization] → Harvest
2. Click "Add Harvest Source"
3. Fill in the form:
   - **URL**: Data.gov Search API endpoint with optional query parameters
     - Example: `https://catalog.data.gov/search?q=fish&org_slug=epa&keyword=California&spatial_within=false&spatial_geometry={%22type%22:%22Polygon%22,%22coordinates%22:[[[-127.0,32.5],[-127.0,42.0],[-114.1,42.0],[-114.1,32.5],[-127.0,32.5]]]}`
   - **Title**: Descriptive name for the harvest source
   - **Type**: Select "Data.gov Catalog" (datagov_harvest)
   - **Configuration**: JSON configuration (optional)
   - **Organization**: Select the organization that will own the harvested datasets

## API Endpoint

**URL**: `https://catalog.data.gov/search`

## Query Parameters

Query parameters can be included in the harvest source URL. The harvester preserves ALL query parameters during pagination.

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `q` | string | Full-text search query | `q=water+quality` |
| `org_slug` | string | Filter by organization slug | `org_slug=epa-gov` |
| `keyword` | string/array | Filter by exact keyword match | `keyword=California` |
| `spatial_geometry` | GeoJSON | Filter by spatial geometry | See example below |
| `spatial_filter` | string | Filter by spatial type | `spatial_filter=geospatial` |
| `spatial_within` | boolean | Spatial containment (true=within, false=intersects) | `spatial_within=true` |
| `org_type` | string | Filter by organization type | `org_type=Federal+Government` |
| `sort` | string | Sort order (relevance, popularity, last_harvested_date, distance) | `sort=popularity` |
| `per_page` | integer | Results per page (default: 10) | `per_page=100` |

**Example URLs**:

```
# Simple text search
https://catalog.data.gov/search?q=water

# Filter by organization
https://catalog.data.gov/search?q=fish&org_slug=epa

# Complex query with multiple filters and spatial geometry
https://catalog.data.gov/search?q=fish&org_slug=epa&keyword=California&spatial_within=false&spatial_geometry={%22type%22:%22Polygon%22,%22coordinates%22:[[[-127.0,32.53433506002680],[-127.0,42.00956632985810],[-114.13078987213299,42.00956632985810],[-114.13078987213299,32.53433506002680],[-127.0,32.53433506002680]]]}
```

**Note:** For complex spatial queries, URL-encode the GeoJSON geometry parameter (use `%22` for quotes, `%3A` for colons, etc.).

## Configuration Options

The harvester supports JSON configuration via the harvest source config field. All options are optional.

### Harvester Configuration

Inherited from CustomHarvester base class:

```json
{
  "default_tags": [{"name": "federal-data"}, {"name": "datagov"}],
  "clean_tags": true,
  "default_extras": [
    {"key": "harvest_source", "value": "data.gov"}
  ],
  "mapping_fields": {
    "bureauCode": "dcat.bureauCode",
    "programCode": "dcat.programCode"
  },
  "keep_existing_resources": false
}
```

- `default_tags` (array): Tags to add to all harvested datasets
- `clean_tags` (boolean): Sanitize tag names (remove invalid characters)
- `default_extras` (array): Custom extras to add to all datasets
- `mapping_fields` (object): Map additional DCAT-US fields to CKAN extras
- `organizations_filter_include` (array): Whitelist of organization slugs (only harvest these orgs)
- `organizations_filter_exclude` (array): Blacklist of organization slugs (harvest all except these)
- `keep_existing_resources` (boolean): Preserve unmatched existing resources on update

**Note on Organization Filtering:**
- Filtering happens **after** fetching results from Data.gov API
- Use `organizations_filter_include` for whitelist (only specified orgs are harvested)
- Use `organizations_filter_exclude` for blacklist (all orgs except specified are harvested)
- Organization slugs match the `organization.slug` field from Data.gov (e.g., `"epa"`, `"noaa"`)
- For API-level filtering, use the `org_slug` parameter in the URL instead

### Example Configurations

**Basic harvest with tags**:
```json
{
  "default_tags": [{"name": "federal-data"}],
  "clean_tags": true
}
```

**Filter by organization (post-harvest filtering)**:
```json
{
  "organizations_filter_include": ["epa", "noaa", "usgs"],
  "default_tags": [{"name": "federal-science"}]
}
```

**Exclude specific organizations**:
```json
{
  "organizations_filter_exclude": ["gsa", "dhs"],
  "clean_tags": true
}
```

**Map extended DCAT-US fields**:
```json
{
  "mapping_fields": {
    "bureauCode": "dcat.bureauCode",
    "programCode": "dcat.programCode",
    "theme": "dcat.theme",
    "accrualPeriodicity": "dcat.accrualPeriodicity"
  }
}
```

**Map to composite fields** (requires ckanext-scheming):
```json
{
  "composite_field_mapping": [
    {
      "idInfoCitation": {
        "publicationDate": "extras.dcat_modified",
        "title": "extras.landing_page"
      }
    }
  ]
}
```

**Note on composite_field_mapping:**
- Use `extras.{key_name}` to reference converted extras (e.g., `extras.dcat_modified`, `extras.contact_name`)
- The harvester automatically copies converted extras to `source_dict` before applying config processors
- Available extras: `dcat_modified`, `contact_name`, `contact_email`, `landing_page`, `spatial`, `temporal`, `guid`, `datagov_slug`, etc.
- See "Metadata Mapping" section below for complete list of extras

## Metadata Mapping

The harvester maps Data.gov's DCAT-US metadata format to CKAN's internal structure:

### Core Fields

| Data.gov Field | CKAN Field | Notes |
|----------------|------------|-------|
| `title` | `title` | Dataset title |
| `description` | `notes` | Dataset description |
| `keyword[]` | `tags` | Tags (sanitized) |
| `theme[]` | `groups` | Themes mapped to CKAN groups (see note below) |
| `identifier` | extra: `guid` | UUID identifier (used as GUID) |
| `slug` | extra: `datagov_slug` | Human-readable slug |
| `publisher` | extra: `publisher` | Publishing organization name |
| `last_harvested_date` | extra: `source_metadata_modified` | Last harvest date (trimmed to date if midnight) |

**Note on Theme → Group Mapping:**
Data.gov's `theme` field (from both top-level and `dcat.theme`) is automatically mapped to CKAN groups. Theme names are:
- Converted to lowercase
- Spaces replaced with hyphens
- Special characters removed
- Deduplicated if a theme appears in both locations

**Important:** CKAN groups must exist before datasets can be assigned to them. The `RemoteGroups` configuration processor will validate that groups exist and filter out any that don't. To use this feature:
1. Create groups in CKAN matching your Data.gov themes (e.g., `environment`, `health`, `natural-resources`)
2. Themes will automatically be assigned to matching groups during harvest
3. Non-existent groups will be silently skipped

### DCAT-US Core Fields

| Data.gov Field | CKAN Field | Notes |
|----------------|------------|-------|
| `dcat.accessLevel` | extra: `dcat_access_level` | Access level (public, restricted, etc.) |
| `dcat.modified` | extra: `dcat_modified` | Last modified date (trimmed to date if midnight) |
| `dcat.contactPoint.fn` | extra: `contact_name` | Contact person name |
| `dcat.contactPoint.hasEmail` | extra: `contact_email` | Contact email (mailto: removed) |
| `dcat.license` | `license_id` | License (mapped to CKAN license) |
| `spatial_shape` | extra: `spatial` | GeoJSON Polygon (preferred) |
| `dcat.spatial` | extra: `spatial` | Bounding box string (fallback) |
| `spatial_centroid` | extra: `spatial_centroid` | Center point as "lat,lon" |
| `dcat.temporal` | extra: `temporal` | Temporal coverage |
| `dcat.landingPage` | extra: `landing_page` | Dataset landing page URL |

**Note on Spatial Data:**
Data.gov provides spatial data in multiple formats:
- `spatial_shape`: A proper GeoJSON Polygon object (preferred for mapping)
- `dcat.spatial`: A bounding box string like `"west,south,east,north"` (used as fallback)
- `spatial_centroid`: Center point with `lat` and `lon` (stored as `"lat,lon"` string)

The harvester prefers `spatial_shape` for the `spatial` extra as it provides the actual boundary polygon rather than just a bounding box.

**Note on Date Formatting:**
Timestamps at midnight (00:00:00) are automatically trimmed to date-only format for cleaner display:
- `2015-10-02T00:00:00.000+00:00` → `2015-10-02`
- `2015-10-02T14:30:00.000+00:00` → `2015-10-02T14:30:00.000+00:00` (time preserved)

This applies to `dcat_modified` and `source_metadata_modified` extras.

### Resources (Distributions)

| Data.gov Field | CKAN Field | Notes |
|----------------|------------|-------|
| `distribution[].title` | `resource['name']` | Resource name |
| `distribution[].description` | `resource['description']` | Resource description |
| `distribution[].downloadURL` | `resource['url']` | Download URL (preferred) |
| `distribution[].accessURL` | `resource['url']` | Access URL (fallback) |
| `distribution[].format` | `resource['format']` | File format |
| `distribution[].mediaType` | `resource['mimetype']` | MIME type |
| `distribution[].byteSize` | `resource['size']` | File size in bytes |

### Organization Fields

| Data.gov Field | CKAN Field | Notes |
|----------------|------------|-------|
| `organization.name` | extra: `source_organization_name` | Source org name |
| `organization.organization_type` | extra: `source_organization_type` | Organization type |

**Note:** The following Data.gov fields are NOT mapped to extras (available in source but not stored):
- `harvest_record`: URL to harvest metadata page
- `harvest_record_raw`: URL to raw harvest record
- `distribution_titles`: Array of distribution titles (distributions themselves are mapped to resources)
- `popularity`: Popularity score (search metadata, not stored)

### Extended Fields

Additional DCAT-US fields can be mapped using the `mapping_fields` configuration option:

- `dcat.bureauCode`: Bureau codes
- `dcat.programCode`: Program codes
- `dcat.theme`: Theme categories
- `dcat.accrualPeriodicity`: Update frequency
- `dcat.references`: Related documents
- And more...

## Creating Groups for Themes

Data.gov datasets often include `theme` fields that categorize datasets (e.g., "Environment", "Health", "Natural Resources"). The harvester automatically maps these themes to CKAN groups, but the groups must exist in CKAN first.

### Common Data.gov Themes

Common themes found in Data.gov datasets include:
- `environment`
- `health`
- `natural-resources`
- `water-quality`
- `public-safety`
- `transportation`
- `education`
- `energy`
- `agriculture`

### Discovering Themes in Your Harvest

To see what themes are available in your Data.gov query results, check the API response:

```bash
curl "https://catalog.data.gov/search?q=your-query&per_page=10" | \
  jq '.results[].theme[]' | sort -u
```

Or after harvesting, check the logs for group validation messages.

## Architecture

### Class Structure

```
CustomHarvester (base class)
└── DataGovHarvester
    ├── info()
    ├── gather_stage()
    ├── fetch_stage()
    ├── import_stage()
    └── _search_for_datasets()
```

### Harvester Lifecycle

1. **gather_stage**: 
   - Parses source URL and extracts query parameters
   - Fetches all datasets using cursor-based pagination
   - Creates HarvestObject records with status (new/change/delete)
   - Uses `identifier` (UUID) as GUID

2. **fetch_stage**:
   - No-op (data already fetched during gather)

3. **import_stage**:
   - Converts Data.gov format to CKAN format using `datagov_to_ckan()`
   - Applies configuration processors
   - Copies resource IDs for updates
   - Creates or updates CKAN packages

### Pagination

The harvester uses cursor-based pagination to handle large result sets:

1. Initial request with no `after` parameter
2. Response includes `after` cursor if more pages exist
3. Subsequent requests include `after` parameter
4. Loop continues until `after` is absent from response

This is more efficient than offset-based pagination and handles concurrent updates better.

## Troubleshooting

### No datasets found

- Check that the harvest source URL is correct
- Verify query parameters are properly formatted

### Datasets not updating

- Verify the `identifier` field is present in Data.gov responses
- Check that harvest jobs are completing successfully
- Review harvest source status page for errors

### Resource IDs changing

- Ensure resources have stable URLs
- Check that `copy_across_resource_ids()` is working correctly
- Resources are matched by URL + name + format

### Missing metadata

- Verify DCAT-US fields are present in Data.gov response
- Use `mapping_fields` config to map additional fields
- Check converter logs for any mapping errors

### License not mapped

- Add custom license mapping in `map_datagov_license()`
- Or license URL will be stored in extras as fallback

## Implementation Files

- `ckanext/custom_harvest/harvesters/datagov.py`: Main harvester class
- `ckanext/custom_harvest/converter.py`: Data mapping functions (datagov_to_ckan, extract_format, map_datagov_license, munge_tag)
- `ckanext/custom_harvest/tests/harvesters/test_datagov_harvester.py`: Test suite
- `ckanext/custom_harvest/tests/harvesters/mock_datagov.py`: Mock server for testing
- `setup.py`: Entry point registration

## Contributing

When modifying the harvester:

1. Update converter functions in `converter.py` for new field mappings
2. Add test cases to `test_datagov_harvester.py`
3. Update mock datasets in `mock_datagov.py` if needed
4. Run tests to verify changes
5. Update this documentation

## Resources

- [Data.gov Catalog API Documentation](https://resources.data.gov/catalog-api/)
- [DCAT-US Schema](https://resources.data.gov/resources/dcat-us/)
- [CKAN Harvesting Documentation](https://github.com/ckan/ckanext-harvest)
