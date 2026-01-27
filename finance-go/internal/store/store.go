package store

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"finance-go/internal/model"
	"finance-go/internal/analysis"

	_ "modernc.org/sqlite"
)

type Store struct {
	db *sql.DB
}

func New(dbPath string) (*Store, error) {
	// Ensure directory exists
	// Assuming path like /data/finance.db, we want /data
	// For simplicity, we assume the caller handles dir creation or we do it here:
	os.MkdirAll("/data", 0755)

	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, err
	}

	createTxTableSQL := `
	CREATE TABLE IF NOT EXISTS transactions (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		amount_cents INTEGER NOT NULL,
		description TEXT NOT NULL,
		category TEXT NOT NULL,
		trans_type TEXT NOT NULL,
		installments INTEGER DEFAULT 1,
		bank TEXT,
		created_at DATETIME DEFAULT CURRENT_TIMESTAMP
	);
	`
	_, err = db.Exec(createTxTableSQL)
	if err != nil {
		return nil, err
	}

	createSettingsTableSQL := `
	CREATE TABLE IF NOT EXISTS settings (
		key TEXT PRIMARY KEY,
		value TEXT NOT NULL
	);
	`
	_, err = db.Exec(createSettingsTableSQL)
	if err != nil {
		return nil, err
	}

	createCategoriesTableSQL := `
	CREATE TABLE IF NOT EXISTS categories (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		name TEXT UNIQUE NOT NULL,
		budget_cents INTEGER DEFAULT 0,
		alert_threshold INTEGER DEFAULT 70,
		keywords TEXT
	);
	`
	_, err = db.Exec(createCategoriesTableSQL)
	if err != nil {
		return nil, err
	}

	// Sync/Migrate Categories (Upsert Logic)
	// We iterate through our defined map to ensure keywords are up to date.
	// We also insert new categories if they don't exist.
	definedCats := []model.Category{
		// --- Nível 1: Ultra Específicos (Prioridade Máxima) ---
		
		// Pets: Ração de raça grande e vet são caros e fáceis de identificar
		{Name: "Pets", Keywords: "bravecto,simparic,nexgard,ração,veterinario,vet,vacina,banho,tosa,petshop,pet", BudgetCents: 30000},

		// Meta Suíça: Prioridade estratégica
		{Name: "Meta Suíça", Keywords: "alemão,goethe,italki,preply,professor,aula,curso,traducao,validacao,diploma,apostila,euro,wise,cambio,passagem,suíça,zurique,berna", BudgetCents: 100000},

		// Tech Específico (Simulação/Dev)
		{Name: "Tech/Simulação", Keywords: "vatsim,ivao,navigraph,sayintentions,msfs,x-plane,simulador,nvidia,rtx,gpu,steam,aws,ec2,s3,host,dominio", BudgetCents: 50000},

		// Moto/Hobby (Manutenção da Harley é distinta de Uber)
		{Name: "Moto/Hobby", Keywords: "harley,davidson,oficina,peça,pneu,revisao,capacete,luva,jaqueta,oleo,veleiro,marina,barco,sailing", BudgetCents: 50000},

		// --- Nível 2: O "Inimigo" (Comportamental) ---
		
		// Plantão/Rua: Capture isso ANTES de "Mercado" ou "Lazer"
		// Se você pedir Ifood no plantão, é despesa de trabalho/cansaço, não lazer.
		{Name: "Plantão/Rua", Keywords: "qrf,QRF,plantao,ifood,delivery,hamburguer,coxinha,quilo,cafezinho,maquina,lanche,subway,mcdonalds,bk,pizza,dominos,refri", BudgetCents: 30000},

		// --- Nível 3: Genéricos (Só caem aqui se não forem os acima) ---

		// Lazer Social
		{Name: "Social/Lazer", Keywords: "restaurante,oliva,JP,boi,jantar,almoço,rodizio,sushi,outback,bar,cerveja,chopp,vinho,date,cinema,ingresso,show,formatura", BudgetCents: 50000},

		// Transporte Utilitário
		{Name: "Transporte", Keywords: "uber,99,taxi,onibus,metro,combustivel,posto,ipva,pedagio,multa,semparar,seguro", BudgetCents: 80000},

		// Saúde Pessoal
		{Name: "Saúde", Keywords: "farmacia,drogaria,remedio,exame,consulta,psicologo,terapia,academia,suplemento,whey,creatina,gympass,nutri,nutricionista,personal,treino,remo,fut,futevolei,jiu,jiujitsu", BudgetCents: 40000},

		// Casa (Contas)
		{Name: "Casa", Keywords: "aluguel,condominio,luz,agua,internet,claro,iptu,faxina,diarista,dora,rivaldo,eletricista,encanador,getninja,conserto", BudgetCents: 200000},

		// Mercado (O "Sump" de tudo que é comida e não foi filtrado antes)
		{Name: "Mercado", Keywords: "mercado,padaria,pepe,açougue,feira,sacolão,horti,carrefour,pão,leite,fruta,arroz,feijão,compra,semanal,mensal,assai,atacadão,sams,hiperideal,redemix", BudgetCents: 100000},
	}

	for _, s := range definedCats {
		// Try Insert
		_, err := db.Exec("INSERT INTO categories (name, keywords, budget_cents, alert_threshold) VALUES (?, ?, ?, ?) ON CONFLICT(name) DO UPDATE SET keywords=excluded.keywords, budget_cents=excluded.budget_cents", s.Name, s.Keywords, s.BudgetCents, 70)
		if err != nil { log.Printf("Error syncing category %s: %v", s.Name, err) }
	}

	// Ensure 'Outros' exists
	db.Exec("INSERT OR IGNORE INTO categories (name, keywords, budget_cents, alert_threshold) VALUES (?, ?, ?, ?)", "Outros", "", 50000, 70)

	// Set Default Budget if not exists
	_, err = db.Exec(`INSERT OR IGNORE INTO settings (key, value) VALUES ('monthly_budget', '5000')`)
	if err != nil {
	    return nil, err
	}

	return &Store{db: db}, nil
}

func (s *Store) Close() error {
	return s.db.Close()
}

// Settings
func (s *Store) GetBudget() (float64, error) {
	var valStr string
	err := s.db.QueryRow(`SELECT value FROM settings WHERE key = 'monthly_budget'`).Scan(&valStr)
	if err != nil {
		return 5000.0, nil // Default
	}
	var val float64
	fmt.Sscanf(valStr, "%f", &val)
	return val, nil
}

func (s *Store) SetBudget(val float64) error {
	_, err := s.db.Exec(`INSERT OR REPLACE INTO settings (key, value) VALUES ('monthly_budget', ?)`, fmt.Sprintf("%.2f", val))
	return err
}

func (s *Store) GetHourlyWage() (float64, error) {
	var valStr string
	err := s.db.QueryRow(`SELECT value FROM settings WHERE key = 'net_hourly_wage'`).Scan(&valStr)
	if err != nil {
		return 0, nil // Default
	}
	var val float64
	fmt.Sscanf(valStr, "%f", &val)
	return val, nil
}

func (s *Store) SetHourlyWage(val float64) error {
	_, err := s.db.Exec(`INSERT OR REPLACE INTO settings (key, value) VALUES ('net_hourly_wage', ?)`, fmt.Sprintf("%.2f", val))
	return err
}

func (s *Store) GetCategories() ([]model.Category, error) {
	rows, err := s.db.Query(`SELECT id, name, keywords, budget_cents, alert_threshold FROM categories ORDER BY name`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var result []model.Category
	for rows.Next() {
		var c model.Category
		if err := rows.Scan(&c.ID, &c.Name, &c.Keywords, &c.BudgetCents, &c.AlertThreshold); err != nil {
			return nil, err
		}
		result = append(result, c)
	}
	return result, nil
}

func (s *Store) UpdateCategory(id int, budgetCents, threshold int) error {
	_, err := s.db.Exec("UPDATE categories SET budget_cents = ?, alert_threshold = ? WHERE id = ?", budgetCents, threshold, id)
	return err
}

// Transactions CRUD

func (s *Store) GetTransaction(id int) (*model.Transaction, error) {
	row := s.db.QueryRow(`SELECT id, amount_cents, description, category, trans_type, installments, bank, created_at FROM transactions WHERE id = ?`, id)
	var t model.Transaction
	var dateStr string
	err := row.Scan(&t.ID, &t.AmountCents, &t.Description, &t.Category, &t.Type, &t.Installments, &t.Bank, &dateStr)
	if err != nil {
		return nil, err
	}
	t.CreatedAt, _ = parseTimeHelper(dateStr)
	return &t, nil
}

func (s *Store) UpdateTransaction(t *model.TransactionParsed) error {
	// ID is expected in TransactionParsed or separate
	// The model.TransactionParsed doesn't have ID. I should probably extend it or pass ID.
	// Looking at model, let's just pass ID as arg or assume logic in web handler calls this with explicit SQL.
	// Actually, let's redefine the method signature to take ID.
    query := `UPDATE transactions SET amount_cents=?, description=?, category=?, trans_type=?, installments=?, bank=? WHERE id=?`
    _, err := s.db.Exec(query, t.AmountCents, t.Description, t.Category, t.Type, t.Installments, t.Bank, t.ID) // Assuming we add ID to Parsed or pass it separately.
    return err
}

func (s *Store) DeleteTransaction(id int) error {
	_, err := s.db.Exec(`DELETE FROM transactions WHERE id = ?`, id)
	return err
}

func (s *Store) GetAllTransactions() ([]model.Transaction, error) {
	rows, err := s.db.Query(`SELECT id, amount_cents, description, category, trans_type, installments, bank, created_at FROM transactions ORDER BY created_at DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var result []model.Transaction
	for rows.Next() {
		var t model.Transaction
		var dateStr string
		if err := rows.Scan(&t.ID, &t.AmountCents, &t.Description, &t.Category, &t.Type, &t.Installments, &t.Bank, &dateStr); err != nil {
			return nil, err
		}
		t.CreatedAt, _ = parseTimeHelper(dateStr)
		result = append(result, t)
	}
	return result, nil
}

func (s *Store) SaveTransaction(tx *model.TransactionParsed) error {
	query := `INSERT INTO transactions (amount_cents, description, category, trans_type, installments, bank, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)`
	// Force standard SQL datetime format (YYYY-MM-DD HH:MM:SS) so strftime works reliably
	dateStr := time.Now().UTC().Format("2006-01-02 15:04:05")
	_, err := s.db.Exec(query, tx.AmountCents, tx.Description, tx.Category, tx.Type, tx.Installments, tx.Bank, dateStr)
	return err
}

// GetMonthlyTransactions returns transactions for a specific month and year.
// If month is 0, retrieves current month.
func (s *Store) GetMonthlyTransactions(month, year int) ([]model.Transaction, error) {
	// SQLite strftime '%m' is 01-12. '%Y' is YYYY.
	query := `
		SELECT id, amount_cents, description, category, trans_type, installments, bank, created_at 
		FROM transactions 
		WHERE strftime('%m', created_at) = ? AND strftime('%Y', created_at) = ?
		ORDER BY created_at DESC
	`
	
	// Format month as "01", "02"...
	mStr := fmt.Sprintf("%02d", month)
	yStr := fmt.Sprintf("%d", year)

	rows, err := s.db.Query(query, mStr, yStr)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var result []model.Transaction
	for rows.Next() {
		var t model.Transaction
		var dateStr string
		if err := rows.Scan(&t.ID, &t.AmountCents, &t.Description, &t.Category, &t.Type, &t.Installments, &t.Bank, &dateStr); err != nil {
			return nil, err
		}
		t.CreatedAt, _ = parseTimeHelper(dateStr)
		result = append(result, t)
	}
	return result, nil
}

func parseTimeHelper(dateStr string) (time.Time, error) {
	formats := []string{
		"2006-01-02 15:04:05",
		"2006-01-02T15:04:05",
		"2006-01-02T15:04:05Z07:00",
		time.RFC3339,
        "2006-01-02 15:04:05+00:00",
	}
	for _, f := range formats {
		if t, err := time.Parse(f, dateStr); err == nil {
			return t, nil
		}
	}
	return time.Time{}, fmt.Errorf("failed to parse date: %s", dateStr)
}

// GetStats returns aggregated data for charts for the given month/year
func (s *Store) GetStats(month, year int) (model.DashboardStats, error) {
	var stats model.DashboardStats
	mStr := fmt.Sprintf("%02d", month)
	yStr := fmt.Sprintf("%d", year)

	// 1. Total Spent
	err := s.db.QueryRow(`
		SELECT COALESCE(SUM(amount_cents), 0) 
		FROM transactions 
		WHERE strftime('%m', created_at) = ? AND strftime('%Y', created_at) = ?
	`, mStr, yStr).Scan(&stats.TotalSpent)
	if err != nil {
		return stats, err
	}
	stats.TotalSpent = stats.TotalSpent / 100.0 // Convert to float units

	// 2. Global Budget
	budget, _ := s.GetBudget()
	stats.BudgetLimit = budget
	if budget > 0 {
		stats.BudgetUsage = (stats.TotalSpent / budget) * 100
	}
	if stats.BudgetUsage > 100 { stats.BudgetUsage = 100 }

	// 3. Category Breakdown & Data Collection for Projection
	catSpent := make(map[string]int)

	cRows, err := s.db.Query(`
		SELECT category, SUM(amount_cents) 
		FROM transactions 
		WHERE strftime('%m', created_at) = ? AND strftime('%Y', created_at) = ?
		GROUP BY category
	`, mStr, yStr)
	if err != nil {
		return stats, err
	}
	defer cRows.Close()

	for cRows.Next() {
		var cat string
		var val int
		cRows.Scan(&cat, &val)
		stats.Category.Labels = append(stats.Category.Labels, cat)
		stats.Category.Values = append(stats.Category.Values, float64(val)/100.0)
		catSpent[cat] = val
	}

	// 4. Smart Projection Logic
	now := time.Now()
	isCurrentMonth := (month == int(now.Month()) && year == now.Year())
	daysInMonth := time.Date(year, time.Month(month)+1, 0, 0, 0, 0, 0, time.UTC).Day()
	daysPassed := daysInMonth
	if isCurrentMonth {
		daysPassed = now.Day()
		if daysPassed == 0 { daysPassed = 1 }
	}

	// 4. Smart Projection & Insights Logic
	s.generateInsights(&stats, month, year, catSpent)

	// 5. Behavioral Analysis (Engine)
	txs, _ := s.GetMonthlyTransactions(month, year)
	cats, _ := s.GetCategories()
	hourly, _ := s.GetHourlyWage()
	
	stats.Insights = append(stats.Insights, analysis.GenerateInsights(&stats, txs, cats, hourly)...)

	return stats, nil
}

func (s *Store) generateInsights(stats *model.DashboardStats, month, year int, catSpent map[string]int) {
	now := time.Now()
	isCurrentMonth := (month == int(now.Month()) && year == now.Year())
	daysInMonth := time.Date(year, time.Month(month)+1, 0, 0, 0, 0, 0, time.UTC).Day()
	daysPassed := daysInMonth
	
	if isCurrentMonth {
		daysPassed = now.Day()
	}
	if daysPassed == 0 { daysPassed = 1 }

	// Calculate Global Rhythm (Pacing)
	// Example: Day 15/30 (50%) vs Spent 60% of Budget
	daysPct := float64(daysPassed) / float64(daysInMonth)
	if daysPct > 0 && stats.BudgetLimit > 0 {
		usagePct := stats.TotalSpent / stats.BudgetLimit
		pace := usagePct / daysPct // > 1 means spending faster than time passes
		
		if isCurrentMonth {
			if pace > 1.15 {
				// Too fast
				stats.Insights = append(stats.Insights, model.Insight{
					Level: "warning", Icon: "🔥", Title: "Ritmo Acelerado",
					Message: fmt.Sprintf("Hoje é dia %d (%d%% do mês), mas você já usou %d%% do orçamento.", now.Day(), int(daysPct*100), int(usagePct*100)),
				})
			} else if pace < 0.85 && daysPassed > 10 {
				// Saving
				stats.Insights = append(stats.Insights, model.Insight{
					Level: "success", Icon: "🌱", Title: "Ritmo Econômico",
					Message: "Você está gastando num ritmo menor que o passar dos dias. Ótimo para poupar!",
				})
			}
		}
	}

	// Fetch Categories settings
	cats, _ := s.GetCategories()
	var totalProjCents int

	// Set of all category names (Configured + Spent)
	allCats := make(map[string]bool)
	catConfig := make(map[string]model.Category)
	for _, c := range cats {
		allCats[c.Name] = true
		catConfig[c.Name] = c
	}
	for name := range catSpent {
		allCats[name] = true
	}

    // Identificar o "Vilão" (Categoria com maior estouro absoluto)
    var maxOver float64
    var villainCat string

	for name := range allCats {
		spent := catSpent[name] // 0 if not present
		config, hasConfig := catConfig[name]
		
		var projCents int
		if isCurrentMonth {
			// Linear projection: (spent / daysPassed) * daysInMonth
			// Only project if daysPassed > 0
			dailyAvg := float64(spent) / float64(daysPassed)
			projCents = int(dailyAvg * float64(daysInMonth))
		} else {
			projCents = spent
		}
		
		totalProjCents += projCents

		// Category Specific Insights
		if hasConfig && config.BudgetCents > 0 {
			
			// 1. Projection Alert
			if projCents > config.BudgetCents {
				over := float64(projCents - config.BudgetCents) / 100.0
                if over > maxOver {
                    maxOver = over
                    villainCat = name
                }
			} 
            
            // 2. Significant Deviation (Spent vs Monthly budget) - Early Warning
            if isCurrentMonth && daysPassed < 20 {
                // If in first 20 days we already spent > 80% of category budget
                spentPct := float64(spent) / float64(config.BudgetCents)
                if spentPct > 0.80 {
                     stats.Insights = append(stats.Insights, model.Insight{
                        Level: "warning", Icon: "⚠️", Title: "Atenção em " + name,
                        Message: fmt.Sprintf("Você já consumiu %.0f%% da meta de %s e ainda é dia %d.", spentPct*100, name, now.Day()),
                    })
                }
            }
		}
	}
    
    // Add the "Top Villain" insight if significant
    if villainCat != "" && maxOver > 50 { // Only alert if over by R$50+
        stats.Insights = append(stats.Insights, model.Insight{
            Level: "warning", Icon: "📉", Title: "Desvio em " + villainCat,
            Message: fmt.Sprintf("Neste ritmo, %s fechará o mês R$ %.0f acima do planejado.", villainCat, maxOver),
        })
    }

	stats.ProjectedTotal = float64(totalProjCents) / 100.0
	stats.Projected = stats.ProjectedTotal // Bind to legacy field for compatibility

	if stats.ProjectedTotal <= stats.BudgetLimit {
		stats.StatusColor = "green"
	} else {
		stats.StatusColor = "red"
	}
}

// Auto-Categorization Logic

func (s *Store) SuggestCategory(desc string) string {
	cats, err := s.GetCategories()
	if err != nil {
		return ""
	}
	desc = strings.ToLower(desc)
	for _, c := range cats {
		if c.Keywords == "" {
			continue
		}
		parts := strings.Split(c.Keywords, ",")
		for _, p := range parts {
			trimmed := strings.TrimSpace(p)
			if trimmed != "" && strings.Contains(desc, trimmed) {
				return c.Name
			}
		}
	}
	return ""
}

// RecategorizeLegacy specifically targets transactions in "Alimentação" 
// and tries to move them to more specific categories based on keywords.
func (s *Store) RecategorizeLegacy() (int, error) {
	cats, err := s.GetCategories()
	if err != nil {
		return 0, err
	}

	// Only target likely miscategorized items
	rows, err := s.db.Query("SELECT id, description, category FROM transactions WHERE category = 'Alimentação' OR category = ''")
	if err != nil {
		return 0, err
	}
	defer rows.Close()

	count := 0
	type Update struct {
		ID  int
		Cat string
	}
	var updates []Update

	for rows.Next() {
		var id int
		var desc, currentCat string
		if err := rows.Scan(&id, &desc, &currentCat); err != nil {
			continue
		}

		// Local logic repeated to avoid re-fetching categories per row
		var newCat string
		descLower := strings.ToLower(desc)
		for _, c := range cats {
			if c.Keywords == "" || c.Name == "Alimentação" { continue } // Skip self
			parts := strings.Split(c.Keywords, ",")
			for _, p := range parts {
				trimmed := strings.TrimSpace(p)
				if trimmed != "" && strings.Contains(descLower, trimmed) {
					newCat = c.Name
					break
				}
			}
			if newCat != "" { break }
		}

		if newCat != "" && newCat != currentCat {
			updates = append(updates, Update{ID: id, Cat: newCat})
		}
	}

	// Apply updates
	for _, u := range updates {
		_, err := s.db.Exec("UPDATE transactions SET category = ? WHERE id = ?", u.Cat, u.ID)
		if err == nil {
			count++
		}
	}
	return count, nil
}

