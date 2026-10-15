FROM alpine:3.22.2

ARG GO_VERSION=1.25.14
ARG GO_SHA256=a21ae5633a269bcd7e90cf767e48225633795e99d831742cbf3397064fee7712

RUN apk add --no-cache ca-certificates \
    && wget -O /tmp/go.tgz "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" \
    && echo "${GO_SHA256}  /tmp/go.tgz" | sha256sum -c - \
    && tar -C /usr/local -xzf /tmp/go.tgz \
    && rm -f /tmp/go.tgz \
    && mkdir -p /go/src /go/bin \
    && chmod -R 1777 /go \
    && /usr/local/go/bin/go version

ENV GOLANG_VERSION=1.25.14 \
    GO_VERSION=1.25.14 \
    GOTOOLCHAIN=local \
    GOPATH=/go \
    PATH=/go/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

WORKDIR /go

CMD ["/bin/sh"]
