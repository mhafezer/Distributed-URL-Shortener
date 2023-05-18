import sys
import requests
from requests.sessions import Session
from threading import Thread
import time
import random

if (len(sys.argv) < 3):
    print("USAGE python3 make_reqs.py ADDRESS:PORT NUM_REQS NUM_THREADS")
    exit(1)

address = sys.argv[1]
num_requests = int(sys.argv[2])
num_threads = int(sys.argv[3])

shorts = [[] for i in range(num_threads)]
successes_put = [0 for i in range(num_threads)]
fails_put = [0 for i in range(num_threads)]
errors_put = [0 for i in range(num_threads)]
successes_get = [0 for i in range(num_threads)]
fails_get = [0 for i in range(num_threads)]
errors_get = [0 for i in range(num_threads)]

def put_request(addr, num_reqs, id):
    short_urls = []
    success = 0
    fail = 0
    error = 0
    session = requests.Session()
    for i in range(num_reqs):
        short = str(random.getrandbits(128))
        short_urls.append(short)
        long = "http://python-performance.test/"
        try:
            if (session.put("http://" + addr + "/?short=" + short + "&long=" + long).status_code < 400):
                success += 1
            else:
                fail += 1
        except:
            error += 1
    errors_put[id] = error
    shorts[id] = short_urls
    successes_put[id] = success
    fails_put[id] = fail

def get_request(addr, id):
    session = requests.Session()
    success = 0
    fail = 0
    error = 0
    for short in shorts[id]:
        try:
            if (session.get("http://" + addr + "/" + short, allow_redirects=False).status_code < 400):
                success += 1
            else:
                fail += 1
        except:
            error += 1
    errors_get[id] = error
    successes_get[id] = success
    fails_get[id] = fail

threads = []
print("##############################################")
print(f"\033[1mSending {num_requests} PUT requests across {num_threads} threads...\033[0m")
start = time.time()
for i in range(num_threads):
    t = Thread(target=put_request, args=(address, num_requests//num_threads, i))
    threads.append(t)
    t.start()
for t in threads:
    t.join()
end = time.time()
print(f"time taken      \033[1m{end-start} seconds\033[0m")
print(f"\033[92m201 responses   {sum(successes_put)}\033[0m")
print(f"\033[93m400 responses   {sum(fails_put)}")
print(f"\033[91mrequest error   {sum(errors_put)}\033[0m")
print("----------------------------------------------")
threads = []
print(f"\033[1mSending {num_requests} GET requests across {num_threads} threads...\033[0m")
start = time.time()
for i in range(num_threads):
    t = Thread(target=get_request, args=(address, i))
    threads.append(t)
    t.start()
for t in threads:
    t.join()
end = time.time()
print(f"time taken      \033[1m{end-start} seconds\033[0m")
print(f"\033[92m307 responses   {sum(successes_get)}\033[0m")
print(f"\033[93m404 responses   {sum(fails_get)}")
print(f"\033[91mrequest error   {sum(errors_get)}\033[0m")
print("##############################################")