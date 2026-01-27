package telegram

import (
	"fmt"
	"log"
	"os"
	"regexp"
	"strconv"
	"strings"
	"time"

	"finance-go/internal/model"
	"finance-go/internal/store"

	tele "gopkg.in/telebot.v3"
)

// StartBot initiates the Telegram bot in a goroutine.
func StartBot(s *store.Store) {
	botToken := os.Getenv("TELEGRAM_BOT_TOKEN")
	if botToken == "" {
		log.Println("⚠️ AVISO: TELEGRAM_BOT_TOKEN vazio. Bot não vai rodar.")
		return
	}

	pref := tele.Settings{
		Token:  botToken,
		Poller: &tele.LongPoller{Timeout: 10 * time.Second},
	}

	b, err := tele.NewBot(pref)
	if err != nil {
		log.Fatalf("Fatal: Erro ao criar bot Telegram: %v", err)
	}

	b.Handle(tele.OnText, func(c tele.Context) error {
		// Fetch categories for inference
		cats, _ := s.GetCategories()

		parsed, err := parseInput(c.Text(), cats)
		if err != nil {
			return c.Reply(fmt.Sprintf("⚠️ <b>Formato Inválido</b>\n\nErro: %v\n\nExemplo: <code>15.50 padaria itau</code>", err), tele.ModeHTML)
		}

		if err := s.SaveTransaction(parsed); err != nil {
			log.Printf("Error saving transaction: %v", err)
			return c.Reply("❌ Erro de banco de dados.")
		}

		// Feedback
		typeEmoji := "💸"
		if parsed.Type == "Credit" {
			typeEmoji = "💳"
		}

		resp := fmt.Sprintf(
			"✅ <b>Salvo!</b>\n\n💰 <b>R$ %.2f</b>\n📍 %s\n🏷️ %s\n%s %s %s",
			float64(parsed.AmountCents)/100.0,
			parsed.Description,
			parsed.Category,
			typeEmoji,
			parsed.Type,
			parsed.Bank,
		)
		if parsed.Installments > 1 {
			resp += fmt.Sprintf(" (%dx)", parsed.Installments)
		}

		return c.Send(resp, tele.ModeHTML)
	})

	go func() {
		log.Println("🤖 Bot Telegram iniciando polling...")
		b.Start()
	}()
}

// --- Parsing Logic (Ported from prototype) ---

var knownBanks = []string{"itau", "nubank", "bradesco", "inter", "c6", "santander", "uv", "visa", "master"}

func inferCategory(description string, categories []model.Category) string {
	descLower := strings.ToLower(description)
	for _, cat := range categories {
		keywords := strings.Split(cat.Keywords, ",")
		for _, k := range keywords {
			k = strings.TrimSpace(k)
			if k != "" && strings.Contains(descLower, k) {
				return cat.Name
			}
		}
	}
	return "Outros" // Default if no match
}

func parseInput(input string, categories []model.Category) (*model.TransactionParsed, error) {
	// Padrao: VALOR DESCRICAO [MODIFICADOR]
	parts := strings.Fields(input)
	if len(parts) < 2 {
		return nil, fmt.Errorf("formato inválido. Use: VALOR DESCRICAO [MODIFICADOR]")
	}

	// 1. Extrair VALOR
	amountStr := parts[0]
	amountStr = strings.ReplaceAll(amountStr, ",", ".")
	amountFloat, err := strconv.ParseFloat(amountStr, 64)
	if err != nil {
		return nil, fmt.Errorf("valor inválido: %s", amountStr)
	}
	amountCents := int(amountFloat * 100)

	// 2. Identificar Modificadores
	txType := "Debit"
	installments := 1
	bank := ""
	
	descParts := parts[1:]
	
	if len(descParts) > 0 {
		lastPart := strings.ToLower(descParts[len(descParts)-1])
		
		// Checa parcelamento (ex: 10x)
		if matched, _ := regexp.MatchString(`^\d+x$`, lastPart); matched {
			instStr := strings.TrimSuffix(lastPart, "x")
			if i, err := strconv.Atoi(instStr); err == nil {
				installments = i
				if installments > 1 {
					txType = "Credit"
				}
				descParts = descParts[:len(descParts)-1]
				
				// Checa banco antes do parcelamento
				if len(descParts) > 0 {
					potentialBank := strings.ToLower(descParts[len(descParts)-1])
					for _, b := range knownBanks {
						if potentialBank == b {
							bank = b
							txType = "Credit"
							descParts = descParts[:len(descParts)-1]
							break
						}
					}
				}
			}
		} else {
			// Checa apenas banco
			for _, b := range knownBanks {
				if lastPart == b {
					bank = b
					txType = "Credit"
					descParts = descParts[:len(descParts)-1]
					break
				}
			}
		}
	}

	description := strings.Join(descParts, " ")
	category := inferCategory(description, categories)

	return &model.TransactionParsed{
		AmountCents:  amountCents,
		Description:  description,
		Category:     category,
		Type:         txType,
		Installments: installments,
		Bank:         bank, // Bank is a string now
	}, nil
}


