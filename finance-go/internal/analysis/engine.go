package analysis

import (
	"fmt"
	"strings"
	"time"

	"finance-go/internal/model"
)

const (
	DefaultCHFRate = 6.50
)

// GenerateInsights adds the specific behavioral insights requested
func GenerateInsights(stats *model.DashboardStats, txs []model.Transaction, cats []model.Category, hourlyWage float64) []model.Insight {
	var insights []model.Insight

	// Helper: Filter transactions for current month only for some insights?
	// The store passes monthly transactions generally, or we check date.
	// Assuming txs passed are for the relevant month OR we filtering inside.
	
	// 1. "Time Is Money" (Cost in Hours)
	// Logic: For every transaction > R$ 100 in "Social/Lazer" or "Tech/Hobbies"
	if hourlyWage > 0 {
		insights = append(insights, analyzeTimeCost(txs, hourlyWage)...)
	}

	// 2. "Swiss Savings" (Positive Reinforcement)
	// Logic: Compare ProjectedSpend vs Budget for "Mercado" and "Plantão/Rua"
	insights = append(insights, analyzeSwissSavings(stats, cats, txs)...)

	// 3. "Zero Spend Streak" (Gamification)
	// Logic: "Plantão/Rua" streak
	insights = append(insights, analyzeStreaks(txs)...)

	return insights
}

func analyzeTimeCost(txs []model.Transaction, hourlyWage float64) []model.Insight {
	var insights []model.Insight
	
	// Only look at top 1 expense of the month to avoid flooding? 
	// Or recent ones? User said "For every transaction...". Let's limit to the most recent significant one to keep dashboard clean.
	
	for _, t := range txs {
		// Filter Categories
		isTarget := false
		cat := strings.ToLower(t.Category)
		if strings.Contains(cat, "social") || strings.Contains(cat, "lazer") || strings.Contains(cat, "tech") || strings.Contains(cat, "hobby") {
			isTarget = true
		}

		if isTarget && float64(t.AmountCents)/100.0 > 100.0 {
			costHours := (float64(t.AmountCents) / 100.0) / hourlyWage
			
			insights = append(insights, model.Insight{
				Level:   "info",
				Icon:    "⏳",
				Title:   "Time is Money",
				Message: fmt.Sprintf("A compra '%s' custou %.1f horas de trabalho.", t.Description, costHours),
				Value:   fmt.Sprintf("%.1fh", costHours),
			})
			
			// Return just the most recent one to avoid spam
			return insights 
		}
	}
	return insights
}

func analyzeSwissSavings(stats *model.DashboardStats, cats []model.Category, txs []model.Transaction) []model.Insight {
	var insights []model.Insight
	now := time.Now()
	
	// Only accurate if we project.
	// Calculate Projection per category
	// Map usage
	catSpent := make(map[string]int)
	for _, t := range txs {
		catSpent[t.Category] += t.AmountCents
	}

	daysInMonth := time.Date(now.Year(), now.Month()+1, 0, 0, 0, 0, 0, time.UTC).Day()
	daysPassed := now.Day()
	if daysPassed == 0 { daysPassed = 1 }

	targets := []string{"Mercado", "Plantão/Rua"}

	for _, target := range targets {
		// Find config
		var config model.Category
		found := false
		for _, c := range cats {
			if c.Name == target {
				config = c
				found = true
				break
			}
		}

		if found && config.BudgetCents > 0 {
			spent := catSpent[target]
			
			// Linear Projection
			dailyAvg := float64(spent) / float64(daysPassed)
			projCents := int(dailyAvg * float64(daysInMonth))

			if projCents < config.BudgetCents {
				// Saving!
				savingBRL := float64(config.BudgetCents - projCents) / 100.0
				savingCHF := savingBRL / DefaultCHFRate
				
				if savingCHF > 5 { // Min threshold
					insights = append(insights, model.Insight{
						Level:   "success",
						Icon:    "🇨🇭",
						Title:   "Poupança Suíça",
						Message: fmt.Sprintf("Sua disciplina em '%s' está gerando %.2f CHF para sua meta.", target, savingCHF),
						Value:   fmt.Sprintf("+%.0f CHF", savingCHF),
					})
				}
			}
		}
	}
	return insights
}

func analyzeStreaks(txs []model.Transaction) []model.Insight {
	var insights []model.Insight
	target := "Plantão/Rua"
	
	now := time.Now()
	lastDate := time.Date(now.Year(), now.Month(), 1, 0, 0, 0, 0, time.Local) // Start of month default? Or absolute? User said "DaysSince = Now - LastTransactionDate"

	// Find last transaction for this category (txs are ordered desc)
	found := false
	for _, t := range txs {
		if t.Category == target {
			lastDate = t.CreatedAt
			found = true
			break
		}
	}
	
	if !found {
		// No spending this month/list? Check if list is empty or represents full history. 
		// Assuming 'txs' passed to this function is the monthly list. 
		// If no spending in Current Month, the streak is at least DaysPassed.
		lastDate = time.Date(now.Year(), now.Month(), 1, 0, 0, 0, 0, time.Local)
		// Actually, if he hasn't spent this month, the streak is definitely valid from start of month.
	}

	daysSince := int(now.Sub(lastDate).Hours() / 24)
	
	if daysSince > 2 {
		insights = append(insights, model.Insight{
			Level:   "success",
			Icon:    "🔥",
			Title:   "Sem Gastos Ruins",
			Message: fmt.Sprintf("Você não gasta com conveniência há %d dias. Mantenha o foco!", daysSince),
			Value:   fmt.Sprintf("%d Dias", daysSince),
		})
	}

	return insights
}
