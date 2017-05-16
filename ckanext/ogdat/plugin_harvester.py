# -*- coding: utf-8 -*-

import re
import json
from datetime import datetime
import logging
from string import Template
from pylons import config

import ckan.plugins as p

from ckan.lib.base import model
import ckan.lib.helpers as h

from ckanext.spatial.interfaces import ISpatialHarvester
from ckanext.spatial.harvesters.csw import CSWHarvester
from ckanext.spatial.harvesters.base import guess_resource_format

import ckanext.spatial.model.harvested_metadata as s

from ckanext.harvest.model import HarvestSource


log = logging.getLogger(__name__)

KEY_METADATA_POC = 'metadata-point-of-contact'
KEY_RESOURCE_POC = 'resource-point-of-contact'

OGD_FORMAT_CSV = 'csv'
OGD_FORMAT_HTML = 'html'
OGD_FORMAT_JSON = 'json'
OGD_FORMAT_ODT = 'odt'
OGD_FORMAT_ODS = 'ods'
OGD_FORMAT_RDF = 'rdf'
OGD_FORMAT_RSS = 'rss'
OGD_FORMAT_ATOM = 'atom'
OGD_FORMAT_TXT = 'txt'
OGD_FORMAT_XML = 'xml'

OGD_FORMAT_GIF = 'gif'
OGD_FORMAT_JPEG = 'jpeg'
OGD_FORMAT_PNG = 'png'
OGD_FORMAT_SVG = 'svg+xml'
OGD_FORMAT_TIFF = 'tiff'

OGD_FORMAT_GML = 'gml'
OGD_FORMAT_GPX = 'gpx'
OGD_FORMAT_KML = 'kml'
OGD_FORMAT_KMZ = 'kmz'
OGD_FORMAT_GEORSS = 'rss+xml'
OGD_FORMAT_SHP = 'shp'
OGD_FORMAT_GEOJSON = 'json'

OGD_SERVICE_WMS_GETCAPA = 'wms'
OGD_SERVICE_WFS_GETCAPA = 'wfs'

map_ext_type = {}
for fmt in (
    OGD_FORMAT_CSV,
    OGD_FORMAT_HTML,
    OGD_FORMAT_JSON,
    OGD_FORMAT_ODT,
    OGD_FORMAT_ODS,
    OGD_FORMAT_RDF,
    OGD_FORMAT_RSS,
    OGD_FORMAT_ATOM,
    OGD_FORMAT_TXT,
    OGD_FORMAT_XML,

    OGD_FORMAT_GIF,
    OGD_FORMAT_JPEG,
    OGD_FORMAT_PNG,

    OGD_FORMAT_TIFF,

    OGD_FORMAT_GML,
    OGD_FORMAT_GPX,
    OGD_FORMAT_KML,
    OGD_FORMAT_KMZ,
    OGD_FORMAT_SHP,
    OGD_FORMAT_GEOJSON,
    ):
   map_ext_type[fmt] = fmt

for ext,fmt in ( ('svg', OGD_FORMAT_SVG),):
   map_ext_type[ext] = fmt

class OGDATHarvesterPlugin(p.SingletonPlugin):

    p.implements(ISpatialHarvester, inherit=True)

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
        if element.name == KEY_METADATA_POC:
            log.info('init: Metadata PoC mapping found')
            element.search_paths = ["gmd:contact/gmd:CI_ResponsibleParty"]
            break;

    log.info('init: Adding ISO mapping to resource PoC')

    s.ISODocument.elements.append(
        s.ISOResponsibleParty(
            name=KEY_RESOURCE_POC,
            search_paths=[
                "gmd:identificationInfo/gmd:MD_DataIdentification/gmd:pointOfContact/gmd:CI_ResponsibleParty",
                "gmd:identificationInfo/srv:SV_ServiceIdentification/gmd:pointOfContact/gmd:CI_ResponsibleParty",
            ],
            multiplicity="1..*",
        )
    )

    log.info('init: Adding ISO mapping to resource characterset')

    s.ISODocument.elements.append(
        s.ISOElement(
            name="dataset-characterset",
            search_paths=[
                "gmd:identificationInfo/*/gmd:characterSet/gmd:MD_CharacterSetCode/@codeListValue",
                 "gmd:identificationInfo/*/gmd:characterSet/gmd:MD_CharacterSetCode/text()",
            ],
            multiplicity="*",
        )
    )

    log.info('init: Adding ISO mapping to EN title')

    s.ISODocument.elements.append(
        s.ISOElement(
            name="title_en",
            search_paths=[
                "(.)[gmd:language/gmd:LanguageCode/@codeListValue='en']/gmd:identificationInfo/*/gmd:citation/gmd:CI_Citation/gmd:title/gco:CharacterString/text()",
                'gmd:identificationInfo/*/gmd:citation/gmd:CI_Citation/gmd:title/gmd:PT_FreeText/gmd:textGroup/gmd:LocalisedCharacterString[@locale="#EN"]/text()',
            ],
            multiplicity="0..1",
        )
    )

    # gmd:distributionInfo 0..1
    #    /gmd:MD_Distribution
    #        /gmd:transferOptions 0..N
    #            /gmd:MD_DigitalTransferOptions
    #                /transferSize 0..1
    #                /gmd:onLine 0..N
    #                    /gmd:CI_OnlineResource

#        ISOResourceLocator(
#            name="resource-locator",
#            search_paths=[
#                "gmd:distributionInfo/gmd:MD_Distribution/gmd:transferOptions/gmd:MD_DigitalTransferOptions/gmd:onLine/gmd:CI_OnlineResource",
#                "gmd:distributionInfo/gmd:MD_Distribution/gmd:distributor/gmd:MD_Distributor/gmd:distributorTransferOptions/gmd:MD_DigitalTransferOptions/gmd:onLine/gmd:CI_OnlineResource"
#            ],
#            multiplicity="*",
#        ),

    s.ISODocument.elements.append(
        s.ISOElement(
            name="transfer-options",
            search_paths=[
                "gmd:distributionInfo/gmd:MD_Distribution/gmd:transferOptions",
                "gmd:distributionInfo/gmd:MD_Distribution/gmd:distributor/gmd:MD_Distributor/gmd:distributorTransferOptions",
            ],
            multiplicity="*",
            elements = [
                s.ISOElement(
                    name="size",
                    search_paths=[
                        "gmd:MD_DigitalTransferOptions/gmd:transferSize/gco:Real/text()",
                    ],
                    multiplicity="0..1",
                ),
                s.ISOResourceLocator(
                    name="online-resource",
                    search_paths=[
                        "gmd:MD_DigitalTransferOptions/gmd:onLine/gmd:CI_OnlineResource",
                    ],
                    multiplicity="*",
                )
            ]
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
        for srcKey, dstKey, transformer in (
                        ("guid",                  "metadata_identifier", None),
                        ("metadata-date",         "metadata_modified",  self._to_date),
                        ("temporal-extent-begin", "begin_datetime",     self._to_datetime),
                        ("temporal-extent-end",    "end_datetime",      self._to_datetime),
                        ):
            extra_val = h.get_pkg_dict_extra(package_dict, srcKey)
            if extra_val:
                if transformer:
                    extra_val = transformer(extra_val)
                package_dict['extras'].append({'key': dstKey, 'value': extra_val})

        if iso_values.get('topic-category'):
            mapped_ll = [self._map_category(isotc) for isotc in iso_values.get('topic-category')]
            cat = [mapped_cat for catlist in mapped_ll for mapped_cat in catlist ]
            package_dict['extras'].append({'key': 'categorization', 'value': str(cat)})

#        license = iso_values.get('limitations-on-public-access') or \
#                  iso_values.get('access-constraints') or \
#                  iso_values.get('use-constraints') or \
#                  'Creative Commons Namensnennung 3.0 Österreich (CC BY 3.0 AT)'
#        package_dict['license'] = license
        package_dict['license_id'] = 'CC-BY-3.0-AT'

        # 19: MAINTAINER
        maintainer = ''
        maintainer_link = None
        maintainer_mail = None
        for role in ('custodian', 'resourceProvider', 'author', None):
            ind, org, mail, url = self._find_responsible(iso_values[KEY_RESOURCE_POC], role)
            if ind or org:
                maintainer = ind + org
                maintainer_link = url
                maintainer_mail = mail

                break
        package_dict['maintainer'] = maintainer or source_config.get('ogd_maintainer', 'N/A');

        # PUBLISHER
        publisher = ''
        for role in ('publisher', 'pointOfContact', None):
            ind, org, mail, url = self._find_responsible(iso_values[KEY_METADATA_POC], role)
            if ind or org:
                publisher = ind + org
                break
        if not publisher:
            publisher = source_config.get('ogd_publisher', 'N/A');
        package_dict['extras'].append({'key': 'publisher', 'value': publisher})


        # Sanitize tags
        tag_validation_regex = source_config.get('tag_validation_regex', ur'[^\w\d_\ \-\\\']')
        tag_re = re.compile(tag_validation_regex, re.UNICODE)

        tags = []
        if 'tags' in iso_values:
            for tag in iso_values['tags']:
                tag = tag_re.sub(' ', tag)
                tags.append({'name': tag})

            package_dict['tags'] = tags


        ### OPTIONAL ADDITIONAL FIELDS

        package_dict['extras'].append({'key': 'schema_name', 'value': 'OGD Austria Metadata 2.3'})
        package_dict['extras'].append({'key': 'schema_language', 'value': 'ger'})
        package_dict['extras'].append({'key': 'schema_characterset', 'value': 'utf8'})

        # 6: metadata linkage
        metadata_linkage_list = [res.get('href') for res in iso_values['coupled-resource'] if 'href' in res ]
        metadata_linkage_list += [res.get('url') for res in iso_values['resource-locator'] if 'url' in res ]

        if metadata_linkage_list:
            package_dict['extras'].append({'key': 'metadata_linkage', 'value': str(metadata_linkage_list)})

        # 13: maintainer link
        # if existing, already extracted in 19:Maintainer
        if maintainer_link:
            package_dict['extras'].append({'key': 'maintainer_link', 'value': maintainer_link})

        # 22: geographic toponym
        if iso_values['extent-free-text']:
            package_dict['extras'].append({'key': 'geographic_toponym', 'value': ';'.join(iso_values['extent-free-text'])})

        # 23: bbox
        wkt_bbox = self._get_wkt_bbox(iso_values)
        if wkt_bbox:
            package_dict['extras'].append({'key': 'geographic_bbox', 'value': wkt_bbox})

        # 26: update frequency
        if iso_values['frequency-of-update']:
            package_dict['extras'].append({'key': 'geographic_bbox', 'value': self._map_frequency(iso_values['frequency-of-update'])})

        # 27: lineage
        if iso_values['lineage']:
            package_dict['extras'].append({'key': 'lineage_quality', 'value': iso_values['lineage']})

        # 28: english title
        if iso_values['title_en']:
            package_dict['extras'].append({'key': 'en_title_and_desc', 'value': iso_values['title_en']})

        # 30: resource citation
        for role in ('owner', 'author', 'resourceProvider'):
            ind, org, mail, url = self._find_responsible(iso_values[KEY_RESOURCE_POC], role)
            if ind or org:
                source = role +': ' + ind + org
                package_dict['extras'].append({'key': 'license_citation', 'value': source})
                break

        # 33: metadata original portal
        harvest_obj_id = data_dict['harvest_object'].id
        original_url = CSWHarvester().get_original_url(harvest_obj_id)
        package_dict['extras'].append({'key': 'metadata_original_portal', 'value': original_url})

        # 34: maintainer mail
        # if existing, already extracted in 19:Maintainer
        if maintainer_mail:
            package_dict['maintainer_email'] = maintainer_mail

        ### RESOURCES

        date_released = iso_values['date-released'] or iso_values['date-created']
        date_updated = iso_values['date-updated']
        data_lang = iso_values['dataset-language']
        data_char = iso_values['dataset-characterset']

        transfer_options = iso_values['transfer-options']

        resources = []

        log.info("FOUND TRANSFER OPTS: %d" %  len(transfer_options))

        for transfer_option in transfer_options:

            resources_num = len(transfer_option['online-resource'])

            log.info("FOUND ONLINE RESOURCES: %d" %  resources_num)


            for resource_locator in transfer_option['online-resource']:
                # same block as csw harvester
                url = resource_locator.get('url', '').strip()
                if url:
                    resource = {}
                    resource['format'] = guess_resource_format(url) or self._guess_format(resource, resource_locator)
                    if resource['format'] == 'wms' and config.get('ckanext.spatial.harvest.validate_wms', False):
                        # Check if the service is a view service
                        test_url = url.split('?')[0] if '?' in url else url
                        if self._is_wms(test_url):
                            resource['verified'] = True
                            resource['verified_date'] = datetime.now().isoformat()
                # end csw harvester code

                    for key, value in ( 
                                ('url', url),
                                ('name', resource_locator.get('name') or p.toolkit._('Unnamed resource')),
                                ('resource_locator_protocol', resource_locator.get('protocol')),
                                ('resource_locator_function', resource_locator.get('function')),
                                ('created', date_released), # 17: resource created
                                ('last_modified', date_updated), # 18: last modified
                                ):
                        if value:
                            resource[key] = value

                    # 31: language
                    if data_lang:
                        resource['language'] = data_lang[0]

                    # 32: character set
                    if data_char:
                        resource['characterset'] = data_char[0]

                    # 29: resource size
                    if transfer_option['size']:
                        if resources_num == 1:
                            resource['resource_size'] = transfer_option['size'] # check uom
                        else:
                            log.info("Size field found, but too many online-resources")

                    resources.append(resource)

        package_dict['resources'] = resources

        return package_dict


    def _to_date(self, src):
        return self.format_date(src, '%Y-%m-%d')

    def _to_datetime(self, src):
        return self.format_date(src, "%Y-%m-%dT%H:%M:%S")

    def format_date(self, value, out_format='%Y-%m-%d'):

        dateformats = [
            "%Y-%m-%d",
            "%y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S"
        ]

        for date_format in dateformats:
            try:
                date = datetime.strptime(value, date_format)
                return date.strftime(out_format)

            except ValueError:
                pass

        log.warn('Cannot parse date ' + value)

        return value


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

    def _guess_format(self, resource, resource_locator):
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
            resource_format = OGD_SERVICE_WMS_GETCAPA
        # GN link to page
        elif resource_locator.get('protocol','') == 'WWW:LINK-1.0-http--link' :
            resource_type = 'link'
            resource_format = resource.get('format')  # take original value if any
        #    resource_format = 'WMS'
        # GN downloadable resource
        elif resource_locator.get('protocol','') == 'WWW:DOWNLOAD-1.0-http--download':
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
                 resource_format = OGD_FORMAT_TIFF
        elif resource_locator.get('protocol','') == 'FILE:GEO':
            if resource_locator.get('mimetype','') in ('application/x-compressed', 'application/zip', 'application/gnutar'):
                 resource_type = 'download'
                 resource_format = OGD_FORMAT_SHP
                 resource['name'] = resource_locator.get('name') or "Shapefile"
                 resource['description'] = resource_locator.get('description') or "Shapefile"
            if resource_locator.get('mimetype','') == 'image/x-tiff':
                 resource_type = 'download'
                 resource_format = OGD_FORMAT_TIFF
                 resource['name'] = resource_locator.get('name') or "File raster"
                 resource['description'] = resource_locator.get('description') or "File raster"
        elif resource_locator.get('protocol','') == 'FILE:RASTER':
            if resource_locator.get('mimetype','') in ('application/x-compressed', 'application/zip', 'application/gnutar'):
                 resource_type = 'download'
                 resource_format = OGD_FORMAT_TIFF
                 resource['name'] = resource_locator.get('name') or "Compressed raster file"
                 resource['description'] = resource_locator.get('description') or "Compressed raster file"
            if resource_locator.get('mimetype','') == 'image/x-tiff':
                 resource_type = 'download'
                 resource_format = OGD_FORMAT_TIFF
                 resource['name'] = resource_locator.get('name') or "Raster file"
                 resource['description'] = resource_locator.get('description') or "Raster file"
        else:
            for ext,fmt in map_ext_type:
                 if resource_locator.get('name').endswith(ext):
                     log.info('Assign fmt %s to ext %s', fmt, ext)
                     resource_format = fmt

        if resource_format:
            log.info('Update fmt = %s ', fmt)
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
                    online = rparty['contact-info']['online-resource']
                    return rparty['individual-name'], \
                           rparty['organisation-name'], \
                           rparty['contact-info']['email'], \
                           online['url'] if isinstance(online, dict) else None

        return None, None, None, None

    def _map_category(self, iso_cat):

        cat_map = {
            'farming':['Land- und Forstwirtschaft','Umwelt'],
            'biota':['Geographie und Planung','Umwelt'],
            'boundaries':['Geographie und Planung','Verwaltung und Politik'],
            'climatologyMeteorologyAtmosphere':['Umwelt'],
            'economy':['Arbeit','Wirtschaft und Tourismus'],
            'elevation':['Geographie und Planung'],
            'environment':['Bildung und Forschung','Land- und Forstwirtschaft','Umwelt','Verwaltung und Politik'],
            'geoscientificInformation':['Bildung und Forschung'],
            'health':['Gesundheit'],
            'imageryBaseMapsEarthCover':['Geographie und Planung'],
            'intelligenceMilitary':['Verwaltung und Politik'],
            'inlandWaters':['Umwelt'],
            'location':['Geographie und Planung'],
            'oceans':['Umwelt'],
            'planningCadastre':['Geographie und Planung','Verwaltung und Politik'],
            'society':['Arbeit','Bevölkerung','Gesellschaft und Soziales'],
            'structure':['Bildung und Forschung','Geographie und Planung','Kunst und Kultur','Sport und Freizeit','Verwaltung und Politik'],
            'transportation':['Verkehr und Technik'],
            'utilitiesCommunication':['Verkehr und Technik']
        }

        return cat_map.get(iso_cat, [iso_cat])

    def _map_frequency(self, iso_freq):

        freq_map = {
            'continual' : 'kontinuierlich',
            'daily' : 'täglich',
            'weekly' : 'wöchentlich',
            'fortnightly' : '14-tägig',
            'monthly' : 'monatlich',
            'quarterly' : 'quartalsweise',
            'biannually' : 'halbjährlich',
            'annually' : 'jährlich',
            'asNeeded' : 'nach Bedarf',
            'irregular' : 'unregelmäßig',
            'notPlanned' : 'nicht geplant',
            'unknown' : 'unbekannt'
        }

        return freq_map.get(iso_freq, iso_freq)

    def _get_wkt_bbox(self, iso_values):

        wkt_template = Template('''
            POLYGON (($xmin $ymin,$xmax $ymin,$xmax $ymax, $xmin $ymax, $xmin $ymin))
        ''')

        if len(iso_values['bbox']) > 0:
            bbox = iso_values['bbox'][0]
            
            try:
                xmin = float(bbox['west'])
                xmax = float(bbox['east'])
                ymin = float(bbox['south'])
                ymax = float(bbox['north'])
            except ValueError, e:
                log.info('Error parsing bbox')
                return None

            else:
                wkt_string = wkt_template.substitute(
                        xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax
                    )

                return wkt_string.strip()
        else:
            return None

