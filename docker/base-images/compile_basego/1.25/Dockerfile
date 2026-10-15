FROM golang:1.25-alpine

RUN apk add --no-cache \
    ca-certificates \
    git \
    make \
    tzdata

ENV GO_VERSION=1.25 \
    GO111MODULE=on \
    GOPROXY=https://goproxy.cn,direct \
    GOPATH=/go \
    PATH=/usr/local/go/bin:/go/bin:$PATH

WORKDIR /src
