## Sylvia dependency: django, neo4j
FROM python:2
maintainer Kun Deng, imkundeng@gmail.com

ENV PATH "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
RUN apt-get update && apt-get install -y  lsof

RUN apt-get install -y unzip && rm -rf /var/lib/apt/lists/*

# Default to UTF-8 file.encoding
ENV LANG C.UTF-8
ENV JAVA_VERSION 7u79
ENV JAVA_DEBIAN_VERSION 7u79-2.5.6-1~deb8u1
RUN apt-get update && apt-get install -y openjdk-7-jdk="$JAVA_DEBIAN_VERSION" && rm -rf /var/lib/apt/lists/*

ENV NEO4J_VERSION 1.9.9
COPY download_and_install_neo4j.sh /
RUN sh /download_and_install_neo4j.sh $NEO4J_VERSION
RUN /neo4j/bin/neo4j start


COPY requirements.txt  /
RUN  pip install -U -r /requirements.txt
RUN  pip install django-celery


COPY sylva /usr/src/app
WORKDIR /usr/src/app
RUN python manage.py syncdb --noinput
RUN python manage.py migrate
RUN echo "from django.contrib.auth.models import User; User.objects.create_superuser('root', 'admin@example.com', '')" | python manage.py shell

EXPOSE 8000 7373
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]




