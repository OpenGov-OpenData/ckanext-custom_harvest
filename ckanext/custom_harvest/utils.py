# -*- coding: utf-8 -*-

import datetime
from dateutil.parser import parse as parse_date

from ckantoolkit import config


def parse_date_iso_format(date):
    '''
    Parses the supplied date and tries to return it as a string in iso format
    '''
    if not date:
        return None
    try:
        default_datetime = datetime.datetime(1, 1, 1, 0, 0, 0)
        _date = parse_date(date, default=default_datetime)
        date_modified = _date.isoformat()
        # solr stores less precise datetime, truncate to 19 charactors
        return date_modified[:19]
    except Exception:
        pass
    return None

def is_xloader_format(resource_format):
    '''
    Determines if the supplied format is accepted by ckanext-xloader
    '''
    DEFAULT_FORMATS = [
        'csv', 'application/csv',
        'xls', 'xlsx', 'tsv',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'ods', 'application/vnd.oasis.opendocument.spreadsheet',
    ]
    xloader_formats = config.get('ckanext.xloader.formats')
    if xloader_formats is not None:
        xloader_formats = xloader_formats.lower().split()
    else:
        xloader_formats = DEFAULT_FORMATS
    if not resource_format:
        return False
    return resource_format.lower() in xloader_formats