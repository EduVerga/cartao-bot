# 🔔 Sistema de Alertas Progressivos

O bot agora possui **6 níveis de alertas** baseados no percentual gasto da caixinha!

## 📊 Níveis de Alerta

### ✅ 0% - 49%: Tudo Sob Controle
```
✅ Tudo sob controle!
💡 Continue assim! 💪
```
**Emoji:** ✅ (verde)

---

### 🟢 50% - 69%: Metade Usada
```
🟢 Metade do limite usado
💡 Você está no caminho certo!
```
**Emoji:** 🟢 (verde)

---

### 🟡 70% - 79%: Atenção
```
🟡 Cuidado: 70% do limite usado
💡 Fique atento aos próximos gastos.
```
**Emoji:** 🟡 (amarelo)

---

### ⚠️ 80% - 89%: Alerta
```
⚠️ ATENÇÃO: 80% do limite usado!
💡 Hora de controlar os gastos nesta categoria!
```
**Emoji:** ⚠️ (laranja)

---

### 🔴 90% - 99%: Alerta Crítico
```
🔴 ALERTA CRÍTICO: 90% do limite usado!
💡 Pega leve! Só restam 10% do orçamento.
```
**Emoji:** 🚨 (vermelho)

---

### 🚨 100%+: Limite Ultrapassado
```
🚨 ATENÇÃO: LIMITE ULTRAPASSADO!
💡 Considere reduzir gastos nesta categoria.
```
**Emoji:** 🚨 (vermelho crítico)

---

## 📱 Exemplo de Mensagem Completa

### Cenário: 45% usado (tudo ok)
```
✅ Compra registrada!

🏪 STARFILE
💰 R$ 450.00
📅 25/11/2025

📦 Mercado
📊 R$ 450.00 / R$ 1000.00
💵 Restante: R$ 550.00
📈 45.0% usado

✅ Tudo sob controle!
💡 Continue assim! 💪
```

### Cenário: 85% usado (alerta)
```
⚠️ Compra registrada!

🏪 MC DONALDS
💰 R$ 850.00
📅 25/11/2025

📦 Alimentação fora de casa
📊 R$ 850.00 / R$ 1000.00
💵 Restante: R$ 150.00
📈 85.0% usado

⚠️ ATENÇÃO: 80% do limite usado!
💡 Hora de controlar os gastos nesta categoria!
```

### Cenário: 105% usado (crítico)
```
🚨 Compra registrada!

🏪 IFOOD
💰 R$ 1050.00
📅 25/11/2025

📦 Alimentação fora de casa
📊 R$ 1050.00 / R$ 1000.00
💵 Restante: R$ -50.00
📈 105.0% usado

🚨 ATENÇÃO: LIMITE ULTRAPASSADO!
💡 Considere reduzir gastos nesta categoria.
```

---

## 🎯 Benefícios

1. **Feedback visual imediato** com emojis coloridos
2. **Mensagens motivacionais** personalizadas
3. **Alertas progressivos** que aumentam conforme o gasto
4. **Ajuda a controlar** os gastos antes de ultrapassar
5. **Incentiva** bons hábitos financeiros

---

## 🔧 Implementação

A função `get_alerta_gasto(percentual)` em [bot_v2.py](bot_v2.py) retorna a mensagem apropriada baseada no percentual.

Todos os locais onde uma transação é registrada agora incluem essas mensagens automaticamente!

---

**Aproveite o sistema de alertas! 🚀**
