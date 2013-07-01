[![Build Status](https://travis-ci.org/Feowl/API.png?branch=develop)](https://travis-ci.org/Feowl/API)

Feowl will provide the citizens, journalists and businesses of Douala, Cameroon, with reliable data about the electricity supply. Local media will leverage a network of SMS-enabled contributors, whom the Feowl platform will automatically poll at regular intervals.

Feowl is financed by the International Press Institute's News Contest.
If you are a developer, a designer, a statistician, an electricity specialist, a venture capitalist or an owl breeder and want to help us make Feowl fly, drop us a line at contact@feowl.com

# Installation 
## Install software dependency 
```
sudo apt-get -y install python-software-properties postgis postgresql-9.1 postgresql-server-dev-9.1 postgresql-contrib-9.1 postgis postgresql-9.1-postgis gdal-bin binutils libgeos-3.2.2 libgeos-c1 libgeos-dev libgdal1-dev libxml2 libxml2-dev libxml2-dev checkinstall proj libpq-dev
```

## Create a contrib directory for PostGis
```
sudo mkdir -p '/usr/share/postgresql/9.1/contrib/postgis-1.5'
```
 
## Fetch, compile and install PostGIS
```
cd /tmp
wget http://postgis.refractions.net/download/postgis-1.5.3.tar.gz
tar zxvf postgis-1.5.3.tar.gz && cd postgis-1.5.3/
sudo ./configure && sudo make && sudo checkinstall --pkgname postgis-1.5.3 --pkgversion 1.5.3-src --default
```
 
# now create the template_postgis database template
```
sudo su postgres -c'createdb -E UTF8 -U postgres template_postgis'
sudo su postgres -c'createlang -d template_postgis plpgsql;'
sudo su postgres -c'psql -U postgres -d template_postgis -c"CREATE EXTENSION hstore;"'
sudo su postgres -c'psql -U postgres -d template_postgis -f /usr/share/postgresql/9.1/contrib/postgis-1.5/postgis.sql'
sudo su postgres -c'psql -U postgres -d template_postgis -f /usr/share/postgresql/9.1/contrib/postgis-1.5/spatial_ref_sys.sql'
sudo su postgres -c'psql -U postgres -d template_postgis -c"select postgis_lib_version();"'
sudo su postgres -c'psql -U postgres -d template_postgis -c "GRANT ALL ON geometry_columns TO PUBLIC;"'
sudo su postgres -c'psql -U postgres -d template_postgis -c "GRANT ALL ON spatial_ref_sys TO PUBLIC;"'
sudo su postgres -c'psql -U postgres -d template_postgis -c "GRANT ALL ON geography_columns TO PUBLIC;"'
```

#### Python Packages (Should use a virtual environment)
```
pip install -r requirements.txt  
```

### Make a real template
```
UPDATE pg_database SET datistemplate = TRUE WHERE datname = 'template_postgis';
```

### Create database user for Django
```
createuser -U postgres --createdb --no-createrole --no-superuser --login --pwprompt feowl_django
```

Enter password *passwd123*

### Create Database
```
createdb --template=template_postgis --owner=feowl_django feowl
```

### Create Database Tables
```
python manage.py syncdb --noinput
python manage.py migrate
python manage.py createsuperuser
```
