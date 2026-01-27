# Dockerfile (Multistage)

# 1. Build Stage
FROM golang:1.23-alpine AS builder

WORKDIR /app

# Instalar dependências para Pure Go (removido gcc/musl-dev pois não precisamos mais de CGO)
# Ca-certificates ainda é necessário para chamadas HTTPS (Telegram bot)
RUN apk add --no-cache ca-certificates tzdata

# Copiar tudo primeiro para garantir que 'go mod tidy' veja o main.go
COPY . .

# Inicializa go.mod se não existir e resolve dependências
RUN [ -f go.mod ] || go mod init finance-go
RUN go mod tidy

# Compilação estática PURE GO (CGO_ENABLED=0 para build rápido e sem gcc)
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o app-financas cmd/server/main.go

# 2. Final Stage
FROM scratch

# Copiar certificados e timezone (necessários pois scratch é vazio)
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo

# Copiar binário do estágio anterior
COPY --from=builder /app/app-financas .

# Nota: Em imagens 'scratch', não podemos rodar 'RUN mkdir'.
# O Docker cria o mount point automaticamente quando o volume é montado.
# Se precisar de subpastas, a app deve criar (como já fazemos no initDB).

EXPOSE 8080

CMD ["./app-financas"]
