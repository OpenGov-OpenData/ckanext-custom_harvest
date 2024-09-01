from ckanext.custom_harvest.utils import (
    parse_date_iso_format,
    is_xloader_format
)


class TestDateIsoFormat(object):

    def test_empty_date(self):
        date = ''
        _date = parse_date_iso_format(date)
        assert _date is None

    def test_date_command(self):
        date = 'Thu Sep 25 10:36:28 2020'
        _date = parse_date_iso_format(date)
        assert _date == '2020-09-25T10:36:28'

    def test_iso_datetime(self):
        date = '2020-02-27T21:26:01.123456'
        _date = parse_date_iso_format(date)
        assert _date == '2020-02-27T21:26:01'

    def test_iso_date(self):
        date = '2020-09-25'
        _date = parse_date_iso_format(date)
        assert _date == '2020-09-25T00:00:00'

    def test_iso_datetime_stripped(self):
        date = '20200925T104941'
        _date = parse_date_iso_format(date)
        assert _date == '2020-09-25T10:49:41'

    def test_date_with_slash(self):
        date = '2020/09/25'
        _date = parse_date_iso_format(date)
        assert _date == '2020-09-25T00:00:00'


class TestIsXloaderFormat(object):

    def test_empty_format(self):
        resource_format = ''
        xloader_format = is_xloader_format(resource_format)
        assert not xloader_format

    def test_csv_format(self):
        resource_format = 'csv'
        xloader_format = is_xloader_format(resource_format)
        assert xloader_format

    def test_xls_format(self):
        resource_format = 'xls'
        xloader_format = is_xloader_format(resource_format)
        assert xloader_format
