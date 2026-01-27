package main

import (
	"log"
	"net/http"

	"finance-go/internal/store"
	"finance-go/internal/telegram"
	"finance-go/internal/web"
)

const (
	DBPath = "/data/finance.db"
	Port   = ":8080"
)

func main() {
	log.Println("🚀 Starting SwissTrack Finance (Portfolio Edition)...")

	// 1. Initialize Store (Dependency Injection)
	db, err := store.New(DBPath)
	if err != nil {
		log.Fatalf("Fatal: Failed to initialize DB: %v", err)
	}
	defer db.Close()

	// 2. Initialize Telegram Bot
	telegram.StartBot(db)

	// 3. Initialize Web Server
	srv, err := web.NewServer(db)
	if err != nil {
		log.Fatalf("Fatal: Failed to initialize Web Server: %v", err)
	}

	// 4. Start HTTP Server
	// We handle /financas/ via Nginx strip-prefix, so the app sees / as root
	// The Router returned by web handles "/" and "/health"
	router := srv.Router()

	log.Printf("🌍 Server running on %s", Port)
	if err := http.ListenAndServe(Port, router); err != nil {
		log.Fatal(err)
	}
}
