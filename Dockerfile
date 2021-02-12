FROM python:3.9.1
RUN pip install --upgrade pip
RUN pip install pipenv
WORKDIR /
ADD . /
RUN pipenv install --system --skip-lock
RUN pip install gunicorn[gevent]
# TODO: remove
EXPOSE 9000
ENTRYPOINT [ "/entrypoint.sh" ]