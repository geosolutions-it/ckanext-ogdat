=============
ckanext-ogdat
=============

Extension for handling metadata according to the specifications of Open Government Data (OGD) in Austria
(OGD Metadata - 2.3).

At the moment only allow to extract in the CSW harvester all the fields described in the specification

Provides one plugin:

- ``ogdat_harvest``: redefines some behaviours of the CSW harvester.
- ``ogdat_theme``: minor GUI customization to better show the OGC related fields in dataset and resource views.


------------
Requirements
------------

Developed and tested on CKAN 2.6.2.

Rquires the *spatial-harvester* plugin to be installed.


------------
Installation
------------

To install *ckanext-ogdat*:

1. Activate your CKAN virtual environment, for example::

     . /usr/lib/ckan/default/bin/activate

2. Install the *ckanext-ogdat* Python package into your virtual environment::

     pip install ckanext-ogdat

3. Add ``ogdat_harvest`` to the ``ckan.plugins`` setting in your CKAN
   config file (by default the config file is located at
   ``/etc/ckan/default/production.ini``).

4. (Optional) Add ``ogdat_theme`` to the ``ckan.plugins`` setting. This plugin will slightly modify the dataset 
   view in order to clearly show the OGD-AT attributes.

5.  Add the property::

     licenses_group_url = file:///PATH/TO/YOUR/ckanext-ogdat/ckan.json

    e.g.::

     licenses_group_url = file:////usr/lib/ckan/default/src/ckanext-ogdat/ckan.json

    If you are already using a license file, please edit it and add the "CC-BY-3.0-AT" license.

6. Restart CKAN. For example if you've deployed CKAN with Apache on Ubuntu::

     sudo service apache2 reload


------------------------
Development Installation
------------------------

To install *ckanext-ogdat* for development, activate your CKAN virtualenv and
do::

    git clone https://github.com/geosolution-it/ckanext-ogdat.git
    cd ckanext-ogdat
    python setup.py develop
    pip install -r dev-requirements.txt

