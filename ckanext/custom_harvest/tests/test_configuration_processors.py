from ckanext.custom_harvest.configuration_processors import (
    DefaultTags, CleanTags,
    DefaultExtras, CopyExtras,
    DefaultGroups, DefaultValues,
    MappingFields, CompositeMapping,
    ContactPoint,
    ResourceFormatOrder,
    KeepExistingResources,
    UploadToDatastore
)


class TestDefaultTags:

    processor = DefaultTags

    def test_validation_correct_format(self):
        list_of_dicts_config = {
            "default_tags": [{"name": "geo"}, {"name": "namibia"}]
        }
        try:
            self.processor.check_config(list_of_dicts_config)
        except ValueError:
            assert False

    def test_validation_wrong_format(self):
        empty_config = {
            "default_tags": ""
        }
        try:
            self.processor.check_config(empty_config)
            assert False
        except ValueError:
            assert True

        string_config = {
            "default_tags": "geo"
        }
        try:
            self.processor.check_config(string_config)
            assert False
        except ValueError:
            assert True

        list_config = {
            "default_tags": ["geo", "namibia"]
        }
        try:
            self.processor.check_config(list_config)
            assert False
        except ValueError:
            assert True

    def test_modify_package_tags(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "tags": [{"name": "russian"}, {"name": "tolstoy"}]
        }
        config = {
            "default_tags": [{"name": "geo"}, {"name": "namibia"}]
        }
        source_dict = {}

        self.processor.modify_package_dict(package, config, source_dict)

        tag_names = sorted([tag_dict["name"] for tag_dict in package["tags"]])
        assert tag_names == ["geo", "namibia", "russian", "tolstoy"]


class TestCleanTags:

    processor = CleanTags

    def test_modify_package_clean_tags(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "tags": [{"name": "tolstoy!"}]
        }
        config = {
            "clean_tags": True
        }
        source_dict = {}

        self.processor.modify_package_dict(package, config, source_dict)

        tag_names = sorted([tag_dict["name"] for tag_dict in package["tags"]])
        assert tag_names == ["tolstoy"]


class TestDefaultGroups:

    processor = DefaultGroups

    def test_modify_package_groups(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "groups": []
        }
        config = {
            "default_groups": ["science", "spend-data"],
            "default_group_dicts": [
                {
                    "id": "b1084f72-292d-11eb-adc1-0242ac120002",
                    "name": "science",
                    "title": "Science",
                    "display_name": "Science",
                    "is_organization": False,
                    "type": "group",
                    "state": "active"
                },
                {
                    "id": "0d7090cc-12c1-4d19-85ba-9bcfc563ab7e",
                    "name": "spend-data",
                    "title": "Spend Data",
                    "display_name": "Spend Data",
                    "is_organization": False,
                    "type": "group",
                    "state": "active"
                }
            ]
        }
        source_dict = {}

        self.processor.modify_package_dict(package, config, source_dict)

        group_names = sorted([group_dict["name"] for group_dict in package["groups"]])
        assert group_names == ["science", "spend-data"]


class TestDefaultExtras:

    processor = DefaultExtras

    def test_validation_correct_format(self):
        dict_config = {
            "default_extras": {
                "encoding": "utf8"
            }
        }
        try:
            self.processor.check_config(dict_config)
        except ValueError:
            assert False

    def test_validation_wrong_format(self):
        empty_config = {
            "default_extras": ""
        }
        try:
            self.processor.check_config(empty_config)
            assert False
        except ValueError:
            assert True

        list_of_dicts_config = {
            "default_extras": [{"encoding": "utf8"}]
        }
        try:
            self.processor.check_config(list_of_dicts_config)
            assert False
        except ValueError:
            assert True

    def test_modify_package_extras(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "extras": []
        }
        config = {
            "default_extras": { "encoding": "utf8" }
        }
        source_dict = {}

        self.processor.modify_package_dict(package, config, source_dict)

        assert package["extras"][0]["key"] == "encoding"
        assert package["extras"][0]["value"] == "utf8"


class TestCopyExtras:
    processor = CopyExtras

    def test_validation_correct_format(self):
        dict_config = {
            "copy_extras": True
        }
        try:
            self.processor.check_config(dict_config)
        except ValueError:
            assert False

    def test_validation_wrong_format(self):
        empty_config = {
            "copy_extras": ""
        }
        try:
            self.processor.check_config(empty_config)
            assert False
        except ValueError:
            assert True

        list_of_dicts_config = {
            "copy_extras": [{"key": True}]
        }
        try:
            self.processor.check_config(list_of_dicts_config)
            assert False
        except ValueError:
            assert True

    def test_modify_package_copy_extras(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "extras": []
        }
        config = {
            "copy_extras": True
        }
        source_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "extras": [
                {"key": "encoding", "value": "utf8"},
                {"key": "frequency-of-update", "value": "monthly"}
            ]
        }

        self.processor.modify_package_dict(package, config, source_dict)

        assert package["extras"][0]["key"] == "encoding"
        assert package["extras"][0]["value"] == "utf8"
        assert package["extras"][1]["key"] == "frequency-of-update"
        assert package["extras"][1]["value"] == "monthly"


class TestDefaultValues:

    processor = DefaultValues

    def test_validation_correct_format(self):
        list_of_dicts_config = {
            "default_values": [
                { "notes": "Some notes" }
            ]
        }
        try:
            self.processor.check_config(list_of_dicts_config)
        except ValueError:
            assert False

    def test_validation_wrong_format(self):
        empty_config = {
            "default_values": ""
        }
        try:
            self.processor.check_config(empty_config)
            assert False
        except ValueError:
            assert True

        dict_config = {
            "default_values": { "notes": "Some notes" }
        }
        try:
            self.processor.check_config(dict_config)
            assert False
        except ValueError:
            assert True

    def test_validation_do_not_set_dataset_id(self):
        id_config = {
            "default_values": [
                { "id": "Dataset ID" }
            ]
        }
        try:
            self.processor.check_config(id_config)
            assert False
        except ValueError:
            assert True

    def test_validation_do_not_set_dataset_name(self):
        name_config = {
            "default_values": [
                { "name": "Dataset Name" }
            ]
        }
        try:
            self.processor.check_config(name_config)
            assert False
        except ValueError:
            assert True

    def test_modify_package_values(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "notes": ""
        }
        config = {
            "default_values": [
                { "notes": "Some notes" },
                { "language": "English" }
            ]
        }
        source_dict = {}

        self.processor.modify_package_dict(package, config, source_dict)

        assert package["notes"] == "Some notes"
        assert package["language"] == "English"


class TestMappingFields:

    processor = MappingFields

    def test_modify_package_with_empty_description_values(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset"
        }
        config = {
            "map_fields": [
                {
                    "default": "No Description",
                    "source": "description",
                    "target": "notes"
                }
            ]
        }
        source_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "description": ""
        }

        self.processor.modify_package_dict(package, config, source_dict)

        assert package["notes"] == "No Description"

    def test_modify_package_with_no_description_values(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset"
        }
        config = {
            "map_fields": [
                {
                    "default": "No Description",
                    "source": "description",
                    "target": "notes"
                }
            ]
        }
        source_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
        }

        self.processor.modify_package_dict(package, config, source_dict)

        assert package["notes"] == "No Description"

    def test_validation_correct_format(self):
        list_of_dicts_config = {
            "map_fields": [
                {
                    "source": "language",
                    "target": "language",
                    "default": "English"
                }
            ]
        }
        try:
            self.processor.check_config(list_of_dicts_config)
        except ValueError:
            assert False

    def test_validation_wrong_format(self):
        empty_config = {
            "map_fields": ""
        }
        try:
            self.processor.check_config(empty_config)
            assert False
        except ValueError:
            assert True

        dict_config = {
            "map_fields": {
                "source": "language",
                "target": "language",
                "default": "English"
            }
        }
        try:
            self.processor.check_config(dict_config)
            assert False
        except ValueError:
            assert True

    def test_validation_do_not_set_dataset_id(self):
        id_config = {
            "map_fields": [
                {
                    "source": "description",
                    "target": "id",
                    "default": "Dataset ID"
                }
            ]
        }
        try:
            self.processor.check_config(id_config)
            assert False
        except ValueError:
            assert True

    def test_validation_do_not_set_dataset_name(self):
        name_config = {
            "map_fields": [
                {
                    "source": "description",
                    "target": "name",
                    "default": "Dataset Name"
                }
            ]
        }
        try:
            self.processor.check_config(name_config)
            assert False
        except ValueError:
            assert True

    def test_modify_package_mapping_values(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset"
        }
        config = {
            "map_fields": [
                {
                    "source": "language",
                    "target": "language",
                    "default": "English"
                }
            ]
        }
        source_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "language": "Spanish"
        }

        self.processor.modify_package_dict(package, config, source_dict)

        assert package["language"] == "Spanish"

    def test_modify_package_mapping_values_with_issued_date(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset"
        }
        config = {
            "map_fields": [
                {
                    "source": "issued_date",
                    "target": "issued_date"
                }
            ]
        }
        source_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "issued": "2021-08-01T20:05:31.000Z"
        }

        self.processor.modify_package_dict(package, config, source_dict)

        assert package["issued_date"] == "2021-08-01"

    def test_modify_package_mapping_values_with_issued_time(self):
        package = {
            "title": "Test Dataset 1",
            "name": "test-dataset-1"
        }
        config = {
            "map_fields": [
                {
                    "source": "issued_time",
                    "target": "issued_time"
                }
            ]
        }
        source_dict = {
            "title": "Test Dataset-1",
            "name": "test-dataset-1",
            "issued": "2021-08-01T20:05:31.000Z"
        }

        self.processor.modify_package_dict(package, config, source_dict)

        assert package["issued_time"] == "20:05:31.000000Z"

    def test_modify_package_mapping_values_with_modified_date(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset"
        }
        config = {
            "map_fields": [
                {
                    "source": "modified_date",
                    "target": "modified_date"
                }
            ]
        }
        source_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "modified": "2022-08-31T11:16:25.000Z"
        }

        self.processor.modify_package_dict(package, config, source_dict)

        assert package["modified_date"] == "2022-08-31"

    def test_modify_package_mapping_values_with_modified_time(self):
        package = {
            "title": "Test Dataset 1",
            "name": "test-dataset-1"
        }
        config = {
            "map_fields": [
                {
                    "source": "modified_time",
                    "target": "modified_time"
                }
            ]
        }
        source_dict = {
            "title": "Test Dataset-1",
            "name": "test-dataset-1",
            "modified": "2022-08-31T11:16:25.000Z"
        }

        self.processor.modify_package_dict(package, config, source_dict)

        assert package["modified_time"] == "11:16:25.000000Z"


class TestCompositeMapping:

    processor = CompositeMapping

    def test_modify_package(self):
        package = {
            "title": "Test Dataset 1",
            "name": "test-dataset-1"
        }

        config = {
            "composite_field_mapping": [
                {
                    "idInfoCitation": {
                        "publicationDate": "metadataPubDate"
                    }
                }
            ]
        }
        source_dict = {
            "title": "Test Dataset-1",
            "name": "test-dataset-1",
            "metadataPubDate": "2023-01-01T18:35:34.000Z"
        }

        self.processor.modify_package_dict(package, config, source_dict)

        assert package["idInfoCitation"] == "{\"publicationDate\": \"2023-01-01T18:35:34.000Z\"}"

    def test_invalid_value(self):
        package = {
            "title": "Test Dataset 2",
            "name": "test-dataset-2"
        }

        config = {
            "composite_field_mapping": [
                {
                    "idInfoCitation": {
                        "publicationDate": "metadataPubDate"
                    }
                }
            ]
        }
        source_dict = {
            "title": "Test Dataset-2",
            "name": "test-dataset-2",
            "metadataPubDate": "null"
        }

        self.processor.modify_package_dict(package, config, source_dict)

        assert package["idInfoCitation"] == "{}"


class TestContactPoint:

    processor = ContactPoint

    def test_validation_correct_format(self):
        dict_config = {
            "contact_point": {
                "default_name": "nonameprovided",
                "source_name": "contact_name",
                "target_name": "contact_name",
                "default_email": "noemailprovided@agency.gov",
                "source_email": "contact_email",
                "target_email": "contact_email"
            }
        }
        try:
            self.processor.check_config(dict_config)
        except ValueError:
            assert False

    def test_validation_wrong_format(self):
        empty_config = {
            "contact_point": ""
        }
        try:
            self.processor.check_config(empty_config)
            assert False
        except ValueError:
            assert True

        list_of_dicts_config = {
            "contact_point": [
                { "default_name": "nonameprovided" },
                { "source_name": "contact_name" },
                { "target_name": "contact_name" },
                { "default_email": "noemailprovided@agency.gov" },
                { "source_email": "contact_email" },
                { "target_email": "contact_email" }
            ]
        }
        try:
            self.processor.check_config(list_of_dicts_config)
            assert False
        except ValueError:
            assert True

    def test_validation_do_not_set_contact_name_to_dataset_id(self):
        id_config = {
            "contact_point": {
                "default_name": "nonameprovided",
                "source_name": "contact_name",
                "target_name": "id",
                "default_email": "noemailprovided@agency.gov",
                "source_email": "contact_email",
                "target_email": "contact_email"
            }
        }
        try:
            self.processor.check_config(id_config)
            assert False
        except ValueError:
            assert True

    def test_validation_do_not_set_contact_name_to_dataset_name(self):
        name_config = {
            "contact_point": {
                "default_name": "nonameprovided",
                "source_name": "contact_name",
                "target_name": "name",
                "default_email": "noemailprovided@agency.gov",
                "source_email": "contact_email",
                "target_email": "contact_email"
            }
        }
        try:
            self.processor.check_config(name_config)
            assert False
        except ValueError:
            assert True

    def test_validation_do_not_set_contact_email_to_dataset_id(self):
        id_config = {
            "contact_point": {
                "default_name": "nonameprovided",
                "source_name": "contact_name",
                "target_name": "contact_name",
                "default_email": "noemailprovided@agency.gov",
                "source_email": "contact_email",
                "target_email": "id"
            }
        }
        try:
            self.processor.check_config(id_config)
            assert False
        except ValueError:
            assert True

    def test_validation_do_not_set_contact_name_to_dataset_name(self):
        name_config = {
            "contact_point": {
                "default_name": "nonameprovided",
                "source_name": "contact_name",
                "target_name": "contact_name",
                "default_email": "noemailprovided@agency.gov",
                "source_email": "contact_email",
                "target_email": "name"
            }
        }
        try:
            self.processor.check_config(name_config)
            assert False
        except ValueError:
            assert True

    def test_modify_package_contact_fields(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset"
        }
        config = {
            "contact_point": {
                "default_name": "nonameprovided",
                "source_name": "contact_name",
                "target_name": "contact_name",
                "default_email": "noemailprovided@agency.gov",
                "source_email": "contact_email",
                "target_email": "contact_email"
            }
        }
        source_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "contact_name": "Jane Doe",
            "contact_email": "jane.doe@agency.gov"
        }

        self.processor.modify_package_dict(package, config, source_dict)

        assert package["contact_name"] == "Jane Doe"
        assert package["contact_email"] == "jane.doe@agency.gov"

    def test_modify_package_contact_fields_from_extras(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset"
        }
        config = {
            "contact_point": {
                "default_name": "nonameprovided",
                "source_name": "extras_contact_name",
                "target_name": "contact_name",
                "default_email": "noemailprovided@agency.gov",
                "source_email": "extras_contact_email",
                "target_email": "contact_email"
            }
        }
        source_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "extras": [
                {"key": "contact_name", "value": "John Doe"},
                {"key": "contact_email", "value": "john.doe@agency.gov"}
            ]
        }

        self.processor.modify_package_dict(package, config, source_dict)

        assert package["contact_name"] == "John Doe"
        assert package["contact_email"] == "john.doe@agency.gov"

    def test_modify_package_contact_fields_from_extras_json(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset"
        }
        config = {
            "contact_point": {
                "default_name": "nonameprovided",
                "source_name": "extras_responsible_party",
                "target_name": "contact_name",
                "default_email": "noemailprovided@agency.gov",
                "source_email": "extras_contact_email",
                "target_email": "contact_email"
            }
        }
        source_dict = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "extras": [
                {"key": "responsible_party", "value": "[{\"name\": \"John Smith\", \"roles\": [\"custodian\"]}]"},
                {"key": "contact_email", "value": "john.smith@agency.gov"}
            ]
        }

        self.processor.modify_package_dict(package, config, source_dict)

        assert package["contact_name"] == "John Smith"
        assert package["contact_email"] == "john.smith@agency.gov"

    def test_modify_package_contact_fields_default_values(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset"
        }
        config = {
            "contact_point": {
                "default_name": "nonameprovided",
                "source_name": "extras_responsible_party",
                "target_name": "contact_name",
                "default_email": "noemailprovided@agency.gov",
                "source_email": "extras_contact_email",
                "target_email": "contact_email"
            }
        }
        source_dict = {
            "title": "Test Dataset",
            "name": "test-dataset"
        }

        self.processor.modify_package_dict(package, config, source_dict)

        assert package["contact_name"] == "nonameprovided"
        assert package["contact_email"] == "noemailprovided@agency.gov"


class TestResourceFormatOrder:

    processor = ResourceFormatOrder

    def test_validation_correct_format(self):
        config = {
            "resource_format_order": ["CSV", "ZIP"]
        }
        try:
            self.processor.check_config(config)
        except ValueError:
            assert False

    def test_validation_wrong_format(self):
        config = {
            "resource_format_order": "csv zip"
        }
        try:
            self.processor.check_config(config)
            assert False
        except ValueError:
            assert True

    def test_modify_package_resource_format_order(self):
        package = {
            "title": "Test Dataset",
            "name": "test-dataset",
            "resources": [
                {
                    "name": "Web Resource",
                    "format": "HTML"
                },
                {
                    "name": "GeoJSON Resource",
                    "format": "GeoJSON"
                },
                {
                    "name": "CSV Resource",
                    "format": "CSV"
                },
                {
                    "name": "ZIP Resource",
                    "format": "ZIP"
                }
            ]
        }
        config = {
            "resource_format_order": ["CSV", "ZIP"]
        }
        source_dict = {}

        self.processor.modify_package_dict(package, config, source_dict)

        res_formats = [res_dict["format"] for res_dict in package["resources"]]
        assert res_formats == ["CSV", "ZIP", "HTML", "GeoJSON"]


class TestKeepExistingResources:

    processor = KeepExistingResources

    def test_validation_correct_format(self):
        config = {
            "keep_existing_resources": True
        }
        try:
            self.processor.check_config(config)
        except ValueError:
            assert False

    def test_validation_wrong_format(self):
        config = {
            "keep_existing_resources": "true"
        }
        try:
            self.processor.check_config(config)
            assert False
        except ValueError:
            assert True


class UploadToDatastore:

    processor = UploadToDatastore

    def test_validation_correct_format(self):
        config = {
            "upload_to_datastore": True
        }
        try:
            self.processor.check_config(config)
        except ValueError:
            assert False

    def test_validation_wrong_format(self):
        config = {
            "upload_to_datastore": "true"
        }
        try:
            self.processor.check_config(config)
            assert False
        except ValueError:
            assert True