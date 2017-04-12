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

3a. Add ``ogdat_harvest`` to the ``ckan.plugins`` setting in your CKAN
   config file (by default the config file is located at
   ``/etc/ckan/default/production.ini``).

3b. Optionally add ``ogdat_theme`` to the ``ckan.plugins`` setting in your CKAN
   config file (by default the config file is located at
   ``/etc/ckan/default/production.ini``).

4. Restart CKAN. For example if you've deployed CKAN with Apache on Ubuntu::

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
