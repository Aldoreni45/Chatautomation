import environ
import psycopg

env = environ.Env()
env.read_env(".env")
url = env("DATABASE_URL").replace("/postgres", "/test_postgres")
c = psycopg.connect(url, connect_timeout=10)
rows = c.execute(
    "select pid, state, wait_event_type, "
    "now() - query_start as age, left(query, 80) "
    "from pg_stat_activity where datname='test_postgres' "
    "and state <> 'idle' order by query_start"
).fetchall()
for r in rows:
    print(r)
c.close()
