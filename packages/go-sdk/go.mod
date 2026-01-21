module github.com/madfam-io/janua/go-sdk

go 1.22

require (
	github.com/golang-jwt/jwt/v5 v5.2.1
	github.com/google/uuid v1.6.0
	github.com/gorilla/websocket v1.5.3
	golang.org/x/oauth2 v0.24.0
)

require (
	golang.org/x/net v0.33.0 // indirect - CVE-2023-45288, CVE-2025-22868, CVE-2025-22870, CVE-2025-22872
	google.golang.org/protobuf v1.36.0 // indirect - CVE-2024-24786
)
