package model

import "time"

// Transaction represents a financial record in the database.
type Transaction struct {
	ID           int
	AmountCents  int
	Description  string
	Category     string
	Type         string // "Debit" or "Credit"
	Installments int
	Bank         string
	CreatedAt    time.Time
}

type Category struct {
	ID             int
	Name           string
	BudgetCents    int
	AlertThreshold int // Percent
	Keywords       string 
}

// TransactionParsed is a helper struct for the parser result before DB insertion.
type TransactionParsed struct {
	ID           int    // 0 for new, set for updates
	AmountCents  int
	Description  string
	Category     string
	Type         string
	Installments int
	Bank         string
}

// Insight represents a generated financial advice or observation.
type Insight struct {
	Level   string // "info", "warning", "success"
	Icon    string // E.g., "💡", "⚠️", "📉"
	Title   string // Short summary
	Message string // Human-readable explanation
	Value   string // The raw data (e.g., "45%")
}

// DashboardStats holds aggregated data for the UI.
type DashboardStats struct {
	TotalSpent      float64
	BudgetLimit     float64
	BudgetUsage     float64
	Projected       float64
	ProjectedTotal  float64
	StatusColor     string    // "green" or "red"
	Insights        []Insight // Structured insights (replaced old Alerts strings)
	Transactions    []TransactionDisplay
	Category LabelsAndValues
	Daily    LabelsAndValues
}

type TransactionDisplay struct {
	ID           int
	Date         string
	Description  string
	Category     string
	Amount       string
	Type         string
	IsCredit     bool
	Installments int
	Bank         string
}

type LabelsAndValues struct {
	Labels []string
	Values []float64
}
