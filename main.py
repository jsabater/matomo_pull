from matomo_pull import (
    data_handling,
    sql_handling,
    settings
)
import os, sys
from dotenv import dotenv_values


def exec(raw_database_variables=None):
    if os.path.exists('.env'):
        raw_database_variables = dotenv_values()

    envvars = settings.init('config.yml', raw_database_variables)

    data_objects = data_handling.set_data_objects_for_sql_conversion(
        settings.config['requests']
    )

    dbschema = envvars.get('POSTGRES_SCHEMA')
    sql_handling.fill_database(data_objects, dbschema)
