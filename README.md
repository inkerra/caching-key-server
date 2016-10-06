## How to run

### Using Docker
```
docker pull mongo
docker run --name mongodb-server -d -p 27017:27017 mongo --noauth --bind_ip=0.0.0.0
# modify MONGODB in server.py to make it use your external IP (instead of mine, 192.168.2.128)
docker build -t cache-key-server .
docker run --name cache-key-server -p 8080:8080 --link mongodb-server:mongo -d cache-key-server
```
### OR Manually

```
# install and run mongodb server
# modify MONGODB in server.py to make it use your IP (instead of mine, 192.168.2.128)
pip install -r requirements.txt
python server.py
```

And then you can fetch from http://localhost:8080/from_cache/?key={key}
