#!/bin/bash
#
# Install Postgres 9.1, PostGIS and create PostGIS template on a clean Ubuntu 11.10 Oneiric Ocelot box
# http://wildfish.com





# now create the template_postgis database template
sudo su; su - postgres
sudo su postgres -c'createdb -E UTF8 -U postgres template_postgis' 
sudo su postgres -c'createlang -d template_postgis plpgsql;' 
sudo su postgres -c'psql -U postgres -d template_postgis -c"CREATE EXTENSION hstore;"' 
sudo su postgres -c'psql -U postgres -d template_postgis -f /usr/share/postgresql/9.1/contrib/postgis-1.5/postgis.sql' 
sudo su c -postgres'psql -U postgres -d template_postgis -f /usr/share/postgresql/9.1/contrib/postgis-1.5/spatial_ref_sys.sql' 
sudo su postgres -c'psql -U postgres -d template_postgis -c"select postgis_lib_version();"' 
sudo su postgres -c'psql -U postgres -d template_postgis -c "GRANT ALL ON geometry_columns TO PUBLIC;"' 
sudo su postgres -c'psql -U postgres -d template_postgis -c "GRANT ALL ON spatial_ref_sys TO PUBLIC;"' 
sudo su postgres -c'psql -U postgres -d template_postgis -c "GRANT ALL ON geography_columns TO PUBLIC;"'
sudo su postgres -c'psql -d postgres -c "UPDATE pg_database SET datistemplate='true' WHERE datname='template_postgis';"'
sudo su postgres -c'psql -d postgres -c "createuser -U postgres --createdb --no-createrole --no-superuser --login --pwprompt feowl_django;"'
sudo su postgres -c'psql -d postgres -c "createdb --template=template_postgis --owner=feowl_django feowl"'


echo "Done!"

echo "Installing Postgres/PostGis..." 


