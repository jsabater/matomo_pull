import urllib3
import sqlalchemy
import os
import yaml
from datetime import datetime, timedelta, date
from .utils import DatabaseAlreadyUpdatedError


def init(data_file='config.yml', raw_database_variables={}):
    global http, config, mtm_vars, connection, raw_start_date
    http = set_http_manager()
    config = set_config(data_file)
    mtm_vars = set_mtm_vars(raw_database_variables)
    raw_start_date = mtm_vars['start_date']
    mtm_vars = check_mtm_vars(mtm_vars)
    connection = set_database_connection(mtm_vars)

    return mtm_vars


def set_http_manager():
    return urllib3.PoolManager()


def set_config(config_file='config.yml'):
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    try:
        (
            config['base_url_parameters'], config['requests']
        )
    except KeyError:
        raise KeyError("Config file wrongly set")

    return config


def set_mtm_vars(data={}):
    """ See: https://www.postgresql.org/docs/current/libpq-envars.html """
    mtm_vars = {
        'base_url': data['base_url'],
        'db_name': data['db_name'],
        'id_site': data['id_site'],
        'start_date': datetime.strptime(data['start_date'], '%Y-%m-%d').date(),
        'end_date': datetime.strptime(data['end_date'], '%Y-%m-%d').date(),
        'token_auth': data['token_auth'],
        'JWT_SECRET_KEY': os.environ.get('JWT_SECRET_KEY'),
        'POSTGRES_USER': os.environ.get('POSTGRES_USER', 'matomo'),
        'POSTGRES_PASSWORD': os.environ.get('POSTGRES_PASSWORD'),
        'POSTGRES_HOST': os.environ.get('POSTGRES_HOST', '127.0.0.1'),
        'POSTGRES_PORT': os.environ.get('POSTGRES_PORT', 5432),
        'POSTGRES_SCHEMA': os.environ.get('POSTGRES_SCHEMA', 'public'),
        'POSTGRES_SSLMODE': os.environ.get('POSTGRES_SSLMODE', 'prefer'),
        'POSTGRES_SSLROOTCERT': os.environ.get('POSTGRES_SSLROOTCERT', '/etc/ssl/certs/ISRG_Root_X1.pem')
    }
    return mtm_vars


def set_database_connection(vars):
    try:
        connection = sqlalchemy.create_engine(
            f"postgresql://{vars['POSTGRES_USER']}:{vars['POSTGRES_PASSWORD']}"
            f"@{vars['POSTGRES_HOST']}:{vars['POSTGRES_PORT']}"
            f"/{vars['db_name']}"
            f"?sslmode={vars['POSTGRES_SSLMODE']}"
            f"&sslrootcert={vars['POSTGRES_SSLROOTCERT']}"
        )
        connection.connect()
    except Exception:
        raise ValueError(
            f"The Postgres database was wrongly configured."
            f"Available variables are {vars}."
        )

    return connection


def check_mtm_vars(mtm_vars):
    mtm_vars = update_dates(mtm_vars)

    if mtm_vars['start_date'] > mtm_vars['end_date']:
        raise DatabaseAlreadyUpdatedError(
            f"""
                Dates aren't set correctly:
                start_date={mtm_vars['start_date']},
                end_date={mtm_vars['end_date']}
            """
        )

    if (
        '' in mtm_vars.values() or not
        mtm_vars.values()
    ):
        raise KeyError(
            f"One or multiple configuration variables aren't set \n"
            f"Configuration variables : {mtm_vars}"
        )

    return mtm_vars


def update_dates(mtm_vars):
    mtm_vars['start_date'] = (
        update_start_date_regarding_database_state(mtm_vars)
    )
    mtm_vars['end_date'] = (
        update_end_date_regarding_database_state(mtm_vars)
    )

    return mtm_vars


def is_database_created(table_name='visits', schema='matomo'):
    try:
        return bool(connection.execute(f"select * from {schema}.{table_name}"))
    except Exception:
        return False


def update_start_date_regarding_database_state(mtm_vars):
    schema = mtm_vars.get('POSTGRES_SCHEMA')
    id_site = mtm_vars.get('id_site')
    if is_database_created(schema=schema):
        last_update = (
            connection.execute(
                f"select date from {schema}.visits where id_site = {id_site} order by date desc limit 1"
            ).fetchall()[0][0]
        ).date()
        return last_update + timedelta(days=1)
    return mtm_vars['start_date']


def update_end_date_regarding_database_state(mtm_vars):
    yesterday = date.today() - timedelta(days=1)
    if mtm_vars['end_date'] <= yesterday:
        return mtm_vars['end_date']
    return yesterday
