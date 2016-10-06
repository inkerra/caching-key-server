FROM python:2.7

MAINTAINER Ana <inkerra@gmail.com>
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY server.py /usr/src/app/
COPY requirements.txt /usr/src/app/

RUN pip install -r requirements.txt

CMD [ "python", "./server.py" ]

EXPOSE 8080
