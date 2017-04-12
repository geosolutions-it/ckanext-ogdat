import re
import json
from datetime import datetime
import logging

import ckan.plugins as plugins

from ckan.lib.base import model
import ckan.lib.helpers as h
from ckan.model import Session

from ckanext.spatial.interfaces import ISpatialHarvester
import ckanext.spatial.model.harvested_metadata as s


from ckanext.harvest.model import HarvestSource


log = logging.getLogger(__name__)


class OGDATHarvesterPlugin(plugins.SingletonPlugin):

    plugins.implements(ISpatialHarvester, inherit=True)

    # GeoNetwork uses this substitutiongroup in online resources
    log.info('init: Adding ISO mapping to gmx:MimeFileType')
    for element in s.ISOResourceLocator.elements:
        if element.name == 'name':
            element.search_paths.append('gmd:name/gmx:MimeFileType/text()')
            break;

    # GeoNetwork sets the resource type in this attribute
    log.info('init: Adding ISO mapping to gmx:MimeFileType/@type')
    s.ISOResourceLocator.elements.append(
            s.ISOElement(
            name="mimetype",
            search_paths=["gmd:name/gmx:MimeFileType/@type"],
            multiplicity="0..1",))

    log.info('init: Replacing ISO mapping to metadata PoC')
    for element in s.ISODocument.elements:
        if element.name == 'metadata-point-of-contact':
            log.info('init: Metadata PoC mapping found')
            element.search_paths = ["gmd:contact/gmd:CI_ResponsibleParty"]
            break;

    log.info('init: Adding ISO mapping to resource PoC')

    s.ISODocument.elements.append(
        s.ISOResponsibleParty(
            name="resource-point-of-contact",
            search_paths=[
                "gmd:identificationInfo/gmd:MD_DataIdentification/gmd:pointOfContact/gmd:CI_ResponsibleParty",
                "gmd:identificationInfo/srv:SV_ServiceIdentification/gmd:pointOfContact/gmd:CI_ResponsibleParty",
            ],
            multiplicity="1..*",
        )
    )
        
    # ISpatialHarvester method
    def get_package_dict(self, context, data_dict):
    	# Getting the harvest source config
    	harvest_source_id = data_dict['harvest_object'].harvest_source_id
    	harvest_source = model.Session.query(HarvestSource).filter(HarvestSource.id == harvest_source_id).first()

    	source_config = json.loads(harvest_source.config) if harvest_source.config else {}

        package_dict = data_dict['package_dict']
        iso_values = data_dict['iso_values']

        # copy extras
        for srcKey, dstKey in (("guid", "metadata_identifier"),
                        ("metadata-date", "metadata_modified"),
                        ("temporal-extent-begin", "begin_datetime"),
                        ("temporal-extent-end", "end_datetime"),
                        ):
            extra_val = h.get_pkg_dict_extra(package_dict, srcKey)
            if extra_val:
                package_dict['extras'].append({'key': dstKey, 'value': extra_val})

        if iso_values.get('topic-category'):
            cat = [(tc + " (To be mapped)") for tc in iso_values.get('topic-category')]
            package_dict['extras'].append({'key': 'categorization', 'value': str(cat)})

        license = iso_values.get('limitations-on-public-access') or \
                  iso_values.get('access-constraints') or \
                  iso_values.get('use-constraints') or \
                  'N/A'
        package_dict['license'] = license

        #metadata-point-of-contact (dataidentification)
        #responsible-organisation   (dataidentification/pointOfContact)
        maintainer = ''
        for role in ('custodian', 'resourceProvider', 'author', None):
            ind, org, mail = self._find_responsible(iso_values['resource-point-of-contact'], role)
            if ind or org:
                maintainer = ind + org
                break
        if not maintainer:
            maintainer = 'default maintainer from config (TODO)'
        package_dict['maintainer'] = maintainer


        publisher = ''
        for role in ('publisher', 'pointOfContact', None):
            ind, org, mail = self._find_responsible(iso_values['metadata-point-of-contact'], role)
            if ind or org:
                publisher = ind + org
                break
        if not publisher:
            publisher = 'default publisher from config (TODO)'

        package_dict['extras'].append({'key': 'publisher', 'value': publisher})



#        ind, org, mail = self._find_responsible(iso_values['metadata-point-of-contact'], 'pointOfContact')
#
#        if ind or org:
#            # log.info('Updating PoC: %s - %s', ind, org )
#            package_dict['author'] = ind + " - " + org
#
#        if mail:
#            package_dict['author_email'] = mail
#
#        for key in ('date-released', 'date-updated'):
#            package_dict['extras'].append({'key': key, 'value': iso_values.get(key)})
#
#        resource_locators = iso_values.get('resource-locator', [])
#        self._update_resources(package_dict['resources'], resource_locators, package_dict)

        # Sanitize tags
        tag_validation_regex = source_config.get('tag_validation_regex', ur'[^\w\d_\ \-\\\']')
        tag_re = re.compile(tag_validation_regex, re.UNICODE)

        tags = []
        if 'tags' in iso_values:
            for tag in iso_values['tags']:
                tag = tag_re.sub(' ', tag)
                tags.append({'name': tag})

            package_dict['tags'] = tags

        return package_dict


    def _update_resources(self, resources, locators, package_dict):
        # @type resources: list
        # @type locators: list

        # l'harvester originale include anche onlineResource esterni a Distribution, che vanno eliminati
        resources_to_delete = []

        for resource in resources:
            locator = self._get_locator_by_url(resource, locators)
            if not locator:
                resources_to_delete.append(resource)
                continue

            # parse GN/ODN specific formats
            self._guess_format(resource, locator, package_dict)

        for delendum in resources_to_delete:
            log.info('Removing resource %s', delendum['url'])
            resources.remove(delendum)


    def _get_locator_by_url(self, resource, locators):
        for locator in locators:
            if resource['url'] == locator.get('url', '').strip():
                return locator

        return None

    def _guess_format(self, resource, resource_locator, package_dict):
        #
        resource_type = None
        resource_format = None

        # resource = {}
#        if package_dict['extras']['resource-type'] == 'service':
#            # Check if the service is a view service
#            test_url = url.split('?')[0] if '?' in url else url
#            if self._is_wms(test_url):
#                resource['verified'] = True
#                resource['verified_date'] = datetime.now().isoformat()
#                resource_format = 'WMS'

        # GN specific WMS type
        if resource_locator.get('protocol','') == 'OGC:WMS-1.3.0-http-get-map' or \
             resource_locator.get('protocol','') == 'OGC:WMS-1.1.1-http-get-map' :

            resource_type='WMS'
            resource_format = 'WMS'
            resource['verified'] = True
            resource['verified_date'] = datetime.now().isoformat()
        # GN link to page
        elif resource_locator.get('protocol','') == 'WWW:LINK-1.0-http--link' :
            resource['verified'] = True
            resource_type = 'link'
            resource_format = resource.get('format')  # take original value if any
        #    resource_format = 'WMS'
        # GN downloadable resource
        elif resource_locator.get('protocol','') == 'WWW:DOWNLOAD-1.0-http--download':
            resource['verified'] = True # ??
            resource['verified_date'] = datetime.now().isoformat() # ??
            if resource_locator.get('mimetype','') in ('application/x-compressed', 'application/zip'):
                 # this is a ZIP file
                 resource_type = 'download'
                 resource_format = 'ZIP'
            if resource_locator.get('mimetype','') == 'application/gnutar':
                 # this is a TGZ file
                 resource_type = 'download'
                 resource_format = 'TGZ'
            if resource_locator.get('mimetype','') == 'application/pdf':
                 resource_type = 'download'
                 resource_format = 'PDF'
            if resource_locator.get('mimetype','') == 'image/x-tiff':
                 resource_type = 'download'
                 resource_format = 'TIFF'
        elif resource_locator.get('protocol','') == 'FILE:GEO':
            resource['verified'] = True # ??
            resource['verified_date'] = datetime.now().isoformat() # ??
            if resource_locator.get('mimetype','') in ('application/x-compressed', 'application/zip', 'application/gnutar'):
                 resource_type = 'download'
                 resource_format = 'SHP'
                 resource['name'] = resource_locator.get('name') or "Shapefile"
                 resource['description'] = resource_locator.get('description') or "Shapefile"
            if resource_locator.get('mimetype','') == 'image/x-tiff':
                 resource_type = 'download'
                 resource_format = 'TIF'
                 resource['name'] = resource_locator.get('name') or "File raster"
                 resource['description'] = resource_locator.get('description') or "File raster"
        elif resource_locator.get('protocol','') == 'FILE:RASTER':
            resource['verified'] = True # ??
            resource['verified_date'] = datetime.now().isoformat() # ??
            if resource_locator.get('mimetype','') in ('application/x-compressed', 'application/zip', 'application/gnutar'):
                 resource_type = 'download'
                 resource_format = 'TIF'
                 resource['name'] = resource_locator.get('name') or "Compressed raster file"
                 resource['description'] = resource_locator.get('description') or "Compressed raster file"
            if resource_locator.get('mimetype','') == 'image/x-tiff':
                 resource_type = 'download'
                 resource_format = 'TIF'
                 resource['name'] = resource_locator.get('name') or "Raster file"
                 resource['description'] = resource_locator.get('description') or "Raster file"

        if resource_type:
            resource.update(
                {
                'resource_type': resource_type,
                'format': resource_format or None,
                })

    def _find_responsible(self, responsible_parties , role):
        '''Find the first responsible info for the given role.
           If no role is given, return first party

        :param responsible_organisations: list of dicts, each with keys
                      including 'organisation-name' and 'role'
        :returns: individual,organization,mail
        '''

        # log.info('Checking %s', responsible_parties)

        if responsible_parties:
            for rparty in responsible_parties:
                if rparty['role'] == role or not role:
                    return rparty['individual-name'], \
                           rparty['organisation-name'], \
                           rparty['contact-info']['email']

        return None, None, None
