
---

# 🇨🇭 SwissTrack Finance: Manual de Comandos

O **SwissTrack** utiliza um sistema de classificação hierárquico. Ele lê a sua descrição e busca palavras-chave específicas para categorizar e etiquetar (tag) o gasto automaticamente.

### 📝 Formato de Envio

Basta enviar uma mensagem no formato:
`VALOR DESCRIÇÃO`

> **Exemplos:**
> `150.00 ração da akita`
> `35 ifood no plantão`
> `1200 curso alemão`

*Obs: Não importa se usar maiúsculas, minúsculas ou acentos.*

---

### 🧠 Como o Robô Pensa (A Hierarquia)

O sistema segue uma ordem de prioridade. Ele tenta encaixar o gasto nas categorias **Específicas** primeiro. Se não encontrar, ele tenta as **Comportamentais**, e por último as **Genéricas**.

#### 1. Prioridades Estratégicas (Nível 1)

Gastos que monitoramos de perto. O robô procura estas palavras primeiro:

* 🐕 **Pets** (Para os Huskys/Akita)
* *Palavras-chave:* `ração`, `vet`, `veterinario`, `bravecto`, `simparic`, `nexgard`, `vacina`, `banho`, `tosa`.


* 🇨🇭 **Meta Suíça** (Investimento no futuro)
* *Palavras-chave:* `alemão`, `goethe`, `italki`, `preply`, `aula`, `curso`, `tradução`, `validação`, `diploma`, `euro`, `wise`, `passagem`, `suíça`.


* ✈️ **Tech & Simulação** (Setup e Voo)
* *Palavras-chave:* `vatsim`, `ivao`, `navigraph`, `sayintentions`, `msfs`, `x-plane`, `nvidia`, `rtx`, `gpu`, `steam`, `aws`, `host`, `dominio`.


* 🏍️ **Moto & Hobby** (Harley e Veleiro)
* *Palavras-chave:* `harley`, `davidson`, `oficina`, `peça`, `pneu`, `capacete`, `jaqueta`, `veleiro`, `marina`, `barco`.



#### 2. O "Inimigo" / Rotina (Nível 2)

Gastos de conveniência ou trabalho. O sistema tenta capturar isso antes de classificar como lazer ou mercado.

* 🏥 **Plantão/Rua** (Gasto de Cansaço/Trabalho)
* *Use quando:* Comer no hospital, pedir delivery por estar de plantão.
* *Palavras-chave:* `plantao`, `qrf`, `ifood`, `delivery`, `hamburguer`, `coxinha`, `cafezinho`, `maquina`, `subway`, `mcdonalds`, `bk`, `dominos`.



#### 3. Categorias Gerais (Nível 3)

Se não for nenhum dos acima, o sistema classifica nestes grupos comuns:

* 🍻 **Social/Lazer:** `restaurante`, `oliva`, `jp`, `boi`, `jantar`, `rodizio`, `sushi`, `outback`, `bar`, `cerveja`, `vinho`, `cinema`, `show`.
* 🚗 **Transporte:** `uber`, `99`, `taxi`, `combustivel`, `posto`, `ipva`, `semparar`, `seguro`.
* 💪 **Saúde/Treino:** `farmacia`, `remedio`, `exame`, `terapia`, `academia`, `whey`, `creatina`, `gympass`, `nutri`, `jiu`, `jiujitsu`.
* 🏠 **Casa:** `aluguel`, `condominio`, `luz`, `agua`, `internet`, `claro`, `faxina`, `dora`, `rivaldo`, `eletricista`, `encanador`.
* 🛒 **Mercado:** (Tudo que sobrar de comida) `mercado`, `padaria`, `pepe`, `açougue`, `feira`, `horti`, `carrefour`, `assai`, `sams`, `hiperideal`, `redemix`.

---

### 💡 Dicas de Uso (Tagging Automático)

O sistema cria **Tags** automaticamente baseado na palavra que você usou.

**Exemplo 1:**

> Você digita: `250.00 jantar no outback`
> * **Categoria:** Social/Lazer
> * **Tags:** `jantar`, `outback`
> * *Por que?* Encontrou "jantar" e "outback" na lista.
> 
> 

**Exemplo 2 (A Diferença de Contexto):**

> Você digita: `50.00 ifood`
> * **Categoria:** Plantão/Rua (e não Lazer!)
> * *Por que?* "Ifood" está configurado como despesa de rotina/plantão.
> 
> 

**Exemplo 3 (Despesa Mista):**

> Você digita: `600.00 revisão harley e gasolina`
> * **Categoria:** Moto/Hobby (Prioridade Nível 1)
> * *Por que?* Embora tenha "gasolina" (Transporte), "Harley" tem prioridade maior na hierarquia.
> 
> 

---

### ❌ O que cai em "Outros"?

Qualquer coisa que não contenha nenhuma das palavras acima.
*Para corrigir:* Se algo cair em "Outros" frequentemente, avise para adicionarmos a palavra-chave no código.