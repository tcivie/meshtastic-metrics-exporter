from psycopg_pool import ConnectionPool


class DBHandler:
    def __init__(self, db_pool: ConnectionPool):
        self.db_pool = db_pool

    def get_connection(self):
        return self.db_pool.getconn()

    def release_connection(self, conn):
        self.db_pool.putconn(conn)

    def execute_db_operation(self, operation):
        with self.db_pool.connection() as conn:
            with conn.cursor() as cur:
                return operation(cur, conn)
