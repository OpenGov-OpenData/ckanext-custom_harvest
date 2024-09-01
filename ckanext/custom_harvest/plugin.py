import ckan.plugins as plugins
from ckanext.custom_harvest import utils


class CustomHarvestPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IPackageController)

    # IPackageController
    def before_index(self, pkg_dict):
        dcat_modified = utils.parse_date_iso_format(pkg_dict.get('extras_modified_date'))
        if dcat_modified:
            if not dcat_modified.endswith('Z'):
                dcat_modified += 'Z'
            pkg_dict['metadata_modified'] = dcat_modified

        dcat_issued = utils.parse_date_iso_format(pkg_dict.get('extras_issued_date'))
        if dcat_issued:
            if not dcat_issued.endswith('Z'):
                dcat_issued += 'Z'
            pkg_dict['metadata_created'] = dcat_issued

        return pkg_dict
