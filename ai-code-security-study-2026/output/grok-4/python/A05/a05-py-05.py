version: '3.8'

services:
  db:
    image: postgres:15
    restart: always
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
      POSTGRES_DB: mydb
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  web:
    build: .
    restart: always
    environment:
      DATABASE_URL: postgresql://user:password@db:5432/mydb
    depends_on:
      - db
    ports:
      - "5000:5000"

volumes:
  postgres_data:
