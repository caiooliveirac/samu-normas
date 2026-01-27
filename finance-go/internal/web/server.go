package web

import (
	"embed"
	"fmt"
	"html/template"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"finance-go/internal/model"
	"finance-go/internal/store"
)

//go:embed templates/*.html
var templateFS embed.FS

type Server struct {
	store *store.Store
	tmpl  *template.Template
}

func NewServer(s *store.Store) (*Server, error) {
	// Custom Functions for Templates
	funcMap := template.FuncMap{
		"div": func(a, b float64) float64 {
			return a / b
		},
		"float64": func(i int) float64 {
			return float64(i)
		},
	}

	// Parse all templates in the embedded FS
	tmpl, err := template.New("base").Funcs(funcMap).ParseFS(templateFS, "templates/*.html")
	if err != nil {
		return nil, fmt.Errorf("failed to parse templates: %v", err)
	}

	return &Server{
		store: s,
		tmpl:  tmpl,
	}, nil
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	// Default to current month/year
	now := time.Now()
	month := int(now.Month())
	year := now.Year()

	// Query Params Override
	if mStr := r.URL.Query().Get("month"); mStr != "" {
		if m, err := strconv.Atoi(mStr); err == nil && m >= 1 && m <= 12 {
			month = m
		}
	}
	
	// Fetch Data
	stats, err := s.store.GetStats(month, year)
	if err != nil {
		log.Printf("Error getting stats: %v", err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	
	txs, err := s.store.GetMonthlyTransactions(month, year)
	if err != nil {
		log.Printf("Error getting transactions: %v", err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	// Prepare Display Data
	stats.Transactions = make([]model.TransactionDisplay, len(txs))
	for i, t := range txs {
		stats.Transactions[i] = model.TransactionDisplay{
			ID:           t.ID,
			Date:         t.CreatedAt.Format("02/01"),
			Description:  t.Description,
			Category:     t.Category,
			Amount:       fmt.Sprintf("%.2f", float64(t.AmountCents)/100.0),
			Type:         t.Type,
			IsCredit:     t.Type == "Credit",
			Installments: t.Installments,
			Bank:         t.Bank,
		}
	}

	// Determine Template (Full vs Partial)
	targetTemplate := "index.html" // Default full page
	
	// Check for HTMX request
	if r.Header.Get("HX-Request") == "true" {
		targetTemplate = "dashboard" // Partial only
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if err := s.tmpl.ExecuteTemplate(w, targetTemplate, stats); err != nil {
		log.Printf("Error executing template: %v", err)
		http.Error(w, "Template Error", http.StatusInternalServerError)
	}
}

// Router returns the httpMux
func (s *Server) Router() http.Handler {
	mux := http.NewServeMux()
	
	// Main Dashboard Handler
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path

		// Normalize Path to support /financas/ prefix (Nginx subdirectory)
		if strings.HasPrefix(path, "/financas") {
			path = strings.TrimPrefix(path, "/financas")
		}
		if path == "" {
			path = "/"
		}
		r.URL.Path = path

		if path == "/" {
			s.ServeHTTP(w, r)
			return
		}

		// Handle Transactions
		if path == "/transactions" || strings.HasPrefix(path, "/transactions/") {
			s.handleTransactions(w, r)
			return
		}

		// Handle Settings
		if path == "/settings" || strings.HasPrefix(path, "/settings/") {
			s.handleSettings(w, r)
			return
		}

		// Handle Export
		if path == "/export" {
			s.handleExport(w, r)
			return
		}
		
		http.NotFound(w, r)
	})

	return mux
}

type TransactionModalData struct {
	model.TransactionDisplay
	Categories []model.Category
}

func (s *Server) handleTransactions(w http.ResponseWriter, r *http.Request) {
    path := r.URL.Path
    // /transactions
    if path == "/transactions" {
        if r.Method == http.MethodPost {
            s.createTransaction(w, r)
            return
        }
        // Maybe method not allowed or just a list (not implemented)
        http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
        return
    }

    // /transactions/...
    sub := path[len("/transactions/"):]
    
    // New Form
    if sub == "new" && r.Method == http.MethodGet {
        cats, _ := s.store.GetCategories()
        // Render Empty Modal
         s.renderModal(w, TransactionModalData{Categories: cats})
         return
    }

    // ID operations
    id, err := strconv.Atoi(sub)
    if err != nil {
        http.NotFound(w, r)
        return
    }

    switch r.Method {
    case http.MethodGet:
        s.editTransactionForm(w, id)
    case http.MethodPut:
        s.updateTransaction(w, r, id)
    case http.MethodDelete:
        s.deleteTransaction(w, r, id)
    default:
        http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
    }
}


func (s *Server) renderModal(w http.ResponseWriter, data any) {
    if err := s.tmpl.ExecuteTemplate(w, "modal_form", data); err != nil {
        log.Printf("Template Error: %v", err)
        http.Error(w, "Template Error", http.StatusInternalServerError)
    }
}

// Helper to bind form to model
func (s *Server) bindTransaction(r *http.Request) (*model.TransactionParsed, error) {
    if err := r.ParseForm(); err != nil {
        return nil, err
    }
    
    amountDiff, _ := strconv.ParseFloat(r.FormValue("amount"), 64)
    amountCents := int(amountDiff * 100)
    
    inst, _ := strconv.Atoi(r.FormValue("installments"))
    if inst < 1 { inst = 1 }

    tx := &model.TransactionParsed{
        AmountCents: amountCents,
        Description: r.FormValue("description"),
        Category:    r.FormValue("category"),
        Type:        r.FormValue("type"), 
        Bank:        r.FormValue("bank"),
        Installments: inst,
    }
    return tx, nil
}

func (s *Server) createTransaction(w http.ResponseWriter, r *http.Request) {
    tx, err := s.bindTransaction(r)
    if err != nil {
        http.Error(w, "Bad Request", http.StatusBadRequest)
        return
    }
    
    if err := s.store.SaveTransaction(tx); err != nil {
        log.Printf("DB Error: %v", err)
        http.Error(w, "DB Error", http.StatusInternalServerError)
        return
    }
    
    // Refresh Dashboard
    s.ServeHTTP(w, r)
}

func (s *Server) editTransactionForm(w http.ResponseWriter, id int) {
    t, err := s.store.GetTransaction(id)
    if err != nil {
        http.NotFound(w, nil)
        return
    }
    cats, _ := s.store.GetCategories()
    
    data := TransactionModalData{
        TransactionDisplay: model.TransactionDisplay{
            ID:           t.ID,
            Description:  t.Description,
            Category:     t.Category,
            Amount:       fmt.Sprintf("%.2f", float64(t.AmountCents)/100.0), // Form input expects float format
            Type:         t.Type,
            Bank:         t.Bank,
            Installments: t.Installments,
        },
        Categories: cats,
    }
    // Re-use logic to format amount properly for input value='10.50'
    
    s.renderModal(w, data)
}


func (s *Server) updateTransaction(w http.ResponseWriter, r *http.Request, id int) {
    tx, err := s.bindTransaction(r)
    if err != nil {
        http.Error(w, "Bad Request", http.StatusBadRequest)
        return
    }
    tx.ID = id
    
    if err := s.store.UpdateTransaction(tx); err != nil {
        log.Printf("Update Error: %v", err)
        http.Error(w, "Update Failed", http.StatusInternalServerError)
        return
    }
    
    // Refresh Dashboard
    s.ServeHTTP(w, r)
}

func (s *Server) deleteTransaction(w http.ResponseWriter, r *http.Request, id int) {
    if err := s.store.DeleteTransaction(id); err != nil {
        log.Printf("Delete Error: %v", err)
        http.Error(w, "Delete Failed", http.StatusInternalServerError)
        return
    }
    s.ServeHTTP(w, r)
}


type SettingsData struct {
	MonthlyBudget float64
	HourlyWage    float64
	Categories    []model.Category
}

func (s *Server) handleSettings(w http.ResponseWriter, r *http.Request) {
    // 0. Recategorize Legacy
    if r.URL.Path == "/settings/recategorize" && r.Method == http.MethodPost {
        count, err := s.store.RecategorizeLegacy()
        if err != nil {
            log.Printf("Recategorize error: %v", err)
            http.Error(w, "Error", http.StatusInternalServerError)
            return
        }
        w.Header().Set("Content-Type", "text/plain")
        fmt.Fprintf(w, "Recategorized %d transactions", count)
        return
    }

	// 1. Update Category (HTMX from row)
	if strings.HasPrefix(r.URL.Path, "/settings/category/") && r.Method == http.MethodPost {
		idStr := strings.TrimPrefix(r.URL.Path, "/settings/category/")
		id, err := strconv.Atoi(idStr)
		if err != nil { return }
		
		if err := r.ParseForm(); err != nil { return }
		
		budgetVal, _ := strconv.ParseFloat(r.FormValue("budget"), 64)
		budgetCents := int(budgetVal * 100)
		
		thresholdVal, _ := strconv.Atoi(r.FormValue("threshold"))
		
		if err := s.store.UpdateCategory(id, budgetCents, thresholdVal); err != nil {
			log.Printf("Error updating category: %v", err)
			http.Error(w, "Error", http.StatusInternalServerError)
			return
		}

		w.WriteHeader(http.StatusOK)
		return
	}

    if r.Method == http.MethodGet {
        budget, _ := s.store.GetBudget()
        hourly, _ := s.store.GetHourlyWage()
        cats, _ := s.store.GetCategories()
        
        data := SettingsData{
            MonthlyBudget: budget,
            HourlyWage:    hourly,
            Categories:    cats,
        }
        
        s.tmpl.ExecuteTemplate(w, "settings", data)
        return
    }
    
    if r.Method == http.MethodPost {
        if err := r.ParseForm(); err != nil { return }
        
        if val := r.FormValue("monthly_budget"); val != "" {
            v, _ := strconv.ParseFloat(val, 64)
            s.store.SetBudget(v)
        }
        
        if val := r.FormValue("hourly_wage"); val != "" {
            v, _ := strconv.ParseFloat(val, 64)
            s.store.SetHourlyWage(v)
        }
        
        // Refresh Dashboard
        s.ServeHTTP(w, r)
    }
}

func (s *Server) handleExport(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "text/csv")
    w.Header().Set("Content-Disposition", "attachment; filename=finance_export.csv")
    
    txs, err := s.store.GetAllTransactions()
    if err != nil { return }
    
    fmt.Fprintln(w, "ID,Date,Description,Category,Type,Amount,Bank,Installments")
    for _, t := range txs {
        fmt.Fprintf(w, "%d,%s,\"%s\",%s,%s,%.2f,%s,%d\n",
            t.ID, t.CreatedAt.Format("2006-01-02 15:04:05"), 
            t.Description, t.Category, t.Type, 
            float64(t.AmountCents)/100.0, t.Bank, t.Installments)
    }
}

