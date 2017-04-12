import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit

import ckan.lib.base as base

import ckanext.ogdat.helpers as helpers


class OGDATThemePlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
#    plugins.implements(plugins.ITemplateHelpers)
#    plugins.implements(plugins.IRoutes, inherit=True)

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')
#        toolkit.add_public_directory(config_, 'public')
#        toolkit.add_resource('fanstatic', 'ogdat')

    # ITemplateHelpers
    def get_helpers(self):
        return {'list_as_li': helpers.list_as_li}

        return map
