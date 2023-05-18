# a writer reads(blpop) from the redis 'cassandra-queue' list and persists data to cassandra
from redis import Redis
from time import sleep
from cassandra.cluster import Cluster
import os

# Connecting to and configuring Cassandra
num_cassandra_nodes = int(os.getenv('CASSANDRA_CLUSTER_SIZE'))
cassandra_ips = []
print(num_cassandra_nodes)
for i in range(num_cassandra_nodes):
    cassandra_ips.append(os.getenv(f'CASSANDRA_NODE_{i}'))
print(cassandra_ips)
cluster = Cluster(cassandra_ips, control_connection_timeout=30, connect_timeout=30)
session = cluster.connect()
session.execute("CREATE KEYSPACE IF NOT EXISTS urls_db WITH REPLICATION = { 'class' : 'SimpleStrategy', 'replication_factor' : 2 };")
session.set_keyspace("urls_db")
session.execute("CREATE TABLE IF NOT EXISTS urls_db.urls (short text PRIMARY KEY, long text)")
put_statement = session.prepare("INSERT INTO urls_db.urls (short, long) values (?, ?) USING TIMESTAMP ?")

# connecting to redis
primary_stream = Redis(host="redis_primary", db=1, socket_connect_timeout=2, socket_timeout=2)


while(True):
    short_url, long_url, timestamp = (None, None, None)
    # try reading in a url pair from the redis queue, otherwise skip iteration
    try:
        url_pair = primary_stream.blpop("cassandra_queue")[1]
        short_url, long_url, timestamp = url_pair.decode().split()[:3]
    except Exception as e:
        print(e)
        sleep(0.05)
        continue
    
    # try until successful to send url pair to cassandra
    while(short_url is not None and long_url is not None):
        try:
            session.execute(put_statement, [short_url, long_url, int(timestamp)])
            print(f"[writer] Sent {short_url} : {long_url} to cassandra...")
            break
        except Exception as e:
            print(e)
            sleep(0.05)




    
