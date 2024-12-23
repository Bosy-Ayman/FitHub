FROM python:3.9-alpine

WORKDIR /app

COPY . .

RUN pip install flask numpy Authlib flask-mail requests flask_bcrypt

EXPOSE 4000

CMD [ "python", "app.py" ]
