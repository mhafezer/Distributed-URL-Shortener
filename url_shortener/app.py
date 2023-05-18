from flask import Flask, request, render_template, redirect
import fastwsgi
from cassandra.cluster import Cluster
from redis import Redis
from datetime import datetime
import re
import os



# Connecting to and configuring Cassandra
num_cassandra_nodes = int(os.getenv('CASSANDRA_CLUSTER_SIZE'))
cassandra_ips = []
if num_cassandra_nodes != 0:
    print(num_cassandra_nodes)
    for i in range(num_cassandra_nodes):
        cassandra_ips.append(os.getenv(f'CASSANDRA_NODE_{i}'))
    print(cassandra_ips)
    cluster = Cluster(cassandra_ips, control_connection_timeout=30, connect_timeout=30)
    session = cluster.connect()
    session.execute("CREATE KEYSPACE IF NOT EXISTS urls_db WITH REPLICATION = { 'class' : 'SimpleStrategy', 'replication_factor' : 2 };")
    session.set_keyspace("urls_db")
    session.execute("CREATE TABLE IF NOT EXISTS urls_db.urls (short text PRIMARY KEY, long text)")
    get_statement = session.prepare("SELECT long FROM urls_db.urls WHERE short=?")
    put_statement = session.prepare("INSERT INTO urls_db.urls (short, long) values (?, ?) USING TIMESTAMP ?")

# Connecting to Redis
primary = Redis(host="redis_primary", db=0,
               socket_connect_timeout=2, socket_timeout=2)
primary_stream = Redis(host="redis_primary", db=1,
                      socket_connect_timeout=2, socket_timeout=2)
secondary = Redis(host="redis_secondary", db=0,
              socket_connect_timeout=2, socket_timeout=2)
app = Flask(__name__)


"""
attempts to query a database to find the log_url matching give short_url
"""
def find_long_url(short_url):
    # try reading from secondarys
    long_url = ""
    try:
        long_url = secondary.get(short_url)
        if long_url is not None:
            return long_url.decode()
    except Exception as e:
        print(e)
        pass

    # if secondarys are down, try reading from primary
    try:
        long_url = primary.get(short_url)
        if long_url is not None:
            return long_url.decode()
    except Exception as e:
        print(e)
        pass

    # if primary and secondarys are down or don't have the short_url, try reading from cassandra 
    try:
        long_url = session.execute(get_statement, [short_url]).one().long
        primary.set(short_url, long_url, 500) # adding to cache
    except Exception as e:
        print(e)
        pass
    return long_url


"""
attemps to send url pair to redis or cassandra if redis is down
"""
def put_url(short_url, long_url):
    # send to primarys key store and queue
    try:
        primary.set(short_url, long_url, ex=500)
        primary_stream.rpush("cassandra_queue", short_url + " " + long_url + " " + str(int(datetime.now().timestamp() * 1000)))
        return True
    except Exception as e:
        print(e)
        pass

    # if primary is down send directly to cassandra
    try:
        session.execute(put_statement, [long_url, short_url, int(datetime.now().timestamp() * 1000)])
        return True
    except Exception as e:
        print(e)
        pass
    return False


"""
long_url must start with http:// or https:// and be less than 2048 chars
"""
def validate_long_url(url):
    if url is None:
        return False
    url_pattern = re.compile(
        "^https?:\/\/[a-zA-Z0-9-._~:/?#\[\]@%!$&'()*+,;=]*$")
    if re.match(pattern=url_pattern, string=url) and len(url) < 2048:
        return True
    return False


"""
short_url must be alphanumeric and less than 128 chars
"""
def validate_short_url(url):
    if url is None:
        return False
    url_pattern = re.compile("^[a-zA-Z0-9]*$")
    if re.match(pattern=url_pattern, string=url) and len(url) < 128:
        return True
    return False


def handle_get(short_url):
    if short_url is not None:
        if not validate_short_url(short_url):
            return "bad request", 400
        long_url = find_long_url(short_url)
        if not long_url:
            return "page not found", 404
        else:
            return redirect(long_url, code=307)
    else:
        # no shorturl query so serve the index page
        return render_template('index.html', message="")


def handle_put(short_url, long_url):
    if (not validate_long_url(long_url) or not validate_short_url(short_url)):
        return "bad request", 400
    if (put_url(short_url, long_url)):
        return "Successfully added Short and Long URL", 200
    return "Failed to add Short and Long URL", 400


@app.route("/", methods=["GET", "PUT"])
@app.route("/<string:short_url>")
def index(short_url=None):
    if (request.method == "GET"):
        return handle_get(short_url)

    args = request.args
    short_url = args.get("short")
    long_url = args.get("long")

    if (request.method == "PUT"):
        return handle_put(short_url, long_url)

    return "Invalid Request Method", 400


if __name__ == "__main__":
    fastwsgi.run(wsgi_app=app, host='0.0.0.0', port=80, loglevel=fastwsgi.LL_NOTICE)
