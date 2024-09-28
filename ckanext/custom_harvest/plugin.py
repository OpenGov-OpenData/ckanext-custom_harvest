import ckan.plugins as plugins
from ckanext.custom_harvest import utils


class CustomHarvestPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IPackageController, inherit=True)

    # IPackageController
    def before_index(self, dataset_dict):
        return self.before_dataset_index(dataset_dict)

    def before_dataset_index(self, pkg_dict):
        source_modified = utils.parse_date_iso_format(pkg_dict.get('extras_source_metadata_modified'))
        if source_modified:
            if not source_modified.endswith('Z'):
                source_modified += 'Z'
            pkg_dict['metadata_modified'] = source_modified

        source_created = utils.parse_date_iso_format(pkg_dict.get('extras_source_metadata_created'))
        if source_created:
            if not source_created.endswith('Z'):
                source_created += 'Z'
            pkg_dict['metadata_created'] = source_created

        return pkg_dict
