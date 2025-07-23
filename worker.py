import os
import redis
from rq import Worker, Queue
from dotenv import load_dotenv
load_dotenv()

redis_url = os.environ["REDIS_URL"]
print("Loaded REDIS_URL:", redis_url)
conn = redis.from_url(redis_url)

if __name__ == '__main__':
    worker = Worker(['default'], connection=conn)
    worker.work()
