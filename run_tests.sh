#!/bin/bash

# Manual test

KEY=666
N=100

echo "Starting server..."
python server.py &
serv_pid="$!"
sleep 5

curls=""
for i in `seq $N`
do
    curl "http://localhost:8080/from_cache?key=$KEY" &
    curls="$curls $!"
done

wait $curls
kill $serv_pid
