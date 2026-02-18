import psycopg2

def connect_to_postgres(host: str, port: int, user: str, password: str, dbname: str):
    """
    Establishes a connection to a PostgreSQL database and returns the connection object.
    
    :param host: Database host address
    :param port: Database port number
    :param user: Database username
    :param password: Database password
    :param dbname: Database name
    :return: psycopg2 connection object
    """
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname
        )
        return conn
    except psycopg2.Error as e:
        raise ConnectionError(f"Failed to connect to the database: {e}")
