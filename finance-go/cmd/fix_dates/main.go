package main

import (
	"database/sql"
	"fmt"
	"log"
	"time"

	_ "modernc.org/sqlite"
)

const DBPath = "/data/finance.db"

type Transaction struct {
	ID        int
	CreatedAt string // Raw string from DB
}

func main() {
	db, err := sql.Open("sqlite", DBPath)
	if err != nil {
		log.Fatalf("Failed to open DB: %v", err)
	}
	defer db.Close()

	// 1. Identify records with bad date format (Go's time.Now().String() format)
	// Example of bad format: 2026-01-18 21:00:00.123456789 -0300 -03 m=+0.001
	// Good format: 2006-01-02 15:04:05 (19 chars)
	
	rows, err := db.Query("SELECT id, created_at FROM transactions")
	if err != nil {
		log.Fatal(err)
	}
	defer rows.Close()

	var toUpdate []Transaction

	for rows.Next() {
		var t Transaction
		if err := rows.Scan(&t.ID, &t.CreatedAt); err != nil {
			log.Println("Scan error:", err)
			continue
		}

		// Check if length is dangerously long or contains " m=" or "T" (ISO format)
		if len(t.CreatedAt) > 19 || Contains(t.CreatedAt, " m=") || Contains(t.CreatedAt, "T") {
			toUpdate = append(toUpdate, t)
		}
	}

	fmt.Printf("Found %d improperly formatted dates.\n", len(toUpdate))

	for _, t := range toUpdate {
		var parsed time.Time
		var err error

		// Try 1: RFC3339Nano (e.g. 2026-01-18T05:57:54.722995225Z)
		parsed, err = time.Parse(time.RFC3339Nano, t.CreatedAt)
		
		// Try 2: Monotonic Go format (spaces)
		if err != nil {
			// Try to grab just the first 19 chars if it looks like "2006-01-02 15:04:05" but has junk after
			if len(t.CreatedAt) >= 19 && !Contains(t.CreatedAt, "T") {
				parsed, err = time.Parse("2006-01-02 15:04:05", t.CreatedAt[:19])
			}
		}

		if err == nil {
			// Success! Convert to pure SQL DateTime
			cleanDate := parsed.Format("2006-01-02 15:04:05")
			fmt.Printf("Fixing ID %d: %s -> %s\n", t.ID, t.CreatedAt, cleanDate)
			_, err := db.Exec("UPDATE transactions SET created_at = ? WHERE id = ?", cleanDate, t.ID)
			if err != nil {
				log.Printf("Failed to update ID %d: %v", t.ID, err)
			}
		} else {
		    fmt.Printf("Skipping unparsable ID %d: %s\n", t.ID, t.CreatedAt)
		}
	}
    
    fmt.Println("Done.")
}

func Contains(s, substr string) bool {
    // Simple implementation since strings.Contains is standard
    for i := 0; i < len(s)-len(substr)+1; i++ {
        if s[i:i+len(substr)] == substr {
            return true
        }
    }
    return false
}
