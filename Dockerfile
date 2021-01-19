FROM python:3.6-slim-stretch

ADD requirements.txt /
RUN apt-get update
RUN apt-get install -y libgl1-mesa-dev \
	libgtk2.0-dev
RUN pip install -r /requirements.txt
ADD . /app
WORKDIR /app

EXPOSE 5000
CMD [ "python" , "app.py"]
