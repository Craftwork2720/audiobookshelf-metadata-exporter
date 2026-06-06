docker buildx build . \
  --platform linux/amd64,linux/arm64 \
  --provenance=false
 
  --tag ghcr.io/craftwork2720/audiobookshelf-meta-exporter:dev \
  --push

docker buildx build . \
  --platform linux/amd64,linux/arm64 \
  --tag ghcr.io/craftwork2720/audiobookshelf-meta-exporter:v0.3.0 \
  --tag ghcr.io/craftwork2720/audiobookshelf-meta-exporter:latest \
  --push