FROM golang:1.20-alpine AS builder

WORKDIR /app

# Copy go mod files
COPY go.mod go.sum* ./
RUN go mod download

# Copy source code
COPY . .

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -o /radius-mcp-server

# Final stage
FROM alpine:3.17

# Install Radius CLI
RUN apk add --no-cache curl && \
    curl -L https://github.com/radius-project/radius/releases/latest/download/rad_linux_amd64.tar.gz | tar xz && \
    mv rad /usr/local/bin/ && \
    chmod +x /usr/local/bin/rad && \
    apk del curl

# Copy the binary from the builder stage
COPY --from=builder /radius-mcp-server /usr/local/bin/

EXPOSE 8085

CMD ["/usr/local/bin/radius-mcp-server"]