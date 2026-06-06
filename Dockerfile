FROM python:3.13-slim-bookworm

# Audiobookshelf DB uses trigger syntax requiring SQLite >= 3.45.
# Bookworm ships 3.40, so pull the newer libsqlite3 from trixie.
RUN echo "deb http://deb.debian.org/debian trixie main" >> /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends -t trixie libsqlite3-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV ABS_DATABASE_PATH="/config/absdatabase.sqlite"
ENV ABS_ITEMS_PATH="/metadata/items"
ENV EXPORT_PATH="/exported"
ENV MATCHER_ENABLED="false"
ENV PORT=8080

EXPOSE 8080
CMD ["waitress-serve", "--host=0.0.0.0", "--port=8080", "--threads=4", "app:app"]
