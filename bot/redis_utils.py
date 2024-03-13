import redis 
from json import loads

#redis_client = redis.StrictRedis(host='127.0.0.1', port='16379', decode_responses=True)
redis_client = redis.StrictRedis(host='redis', port='6379', decode_responses=True)

# Добавление элемента в очередь
def enqueue_photo(user_id, message_id, photo_file_id):
    photo_data = {"user_id": user_id, "message_id": message_id}
    redis_client.rpush("photo_queue", str(photo_data))


# Извлечение и удаление первого элемента из очереди
def dequeue_photo():
    photo_data = redis_client.lpop("photo_queue")
    if photo_data:
        # Вывод данных
        return loads(photo_data.replace("\'", "\""))
    return None

# Посмотреть первый элемент в очереди
def peek_photo():
    photo_data = redis_client.lindex("photo_queue", 0)
    if photo_data:
        return loads(photo_data.replace("\'", "\""))
    return None

# Получение данных о количестве элементов в очереди
def get_queue_length():
    return redis_client.llen("photo_queue")