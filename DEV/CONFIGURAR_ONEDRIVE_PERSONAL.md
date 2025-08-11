# 🔧 Como Configurar OneDrive Personal

## 📋 **Situação Atual**

Você habilitou `onedrive_personal_enabled = true` mas precisa configurar as credenciais. Aqui está o passo-a-passo:

## 🎯 **Diferenças: OneDrive Personal vs Business**

| Aspecto | OneDrive Personal | OneDrive Business |
|---------|-------------------|-------------------|
| **Tipo de Conta** | Microsoft pessoal (@hotmail, @outlook, etc.) | Azure AD empresarial |
| **Autenticação** | OAuth2 pessoal | Client credentials |
| **Configuração** | Mais complexa (precisa autorização manual) | Mais simples (credenciais diretas) |
| **Status Atual** | ⚠️ Parcialmente implementado | ✅ Funcionando |

## ⚙️ **Para Usar OneDrive Personal** 

### **Opção 1: Implementação Completa (Recomendada)**
```ini
[upload_destinations]
# DESABILITA OneDrive Personal temporariamente
onedrive_personal_enabled = false
# USA OneDrive Business que já está funcionando
onedrive_business_enabled = true
local_storage_enabled = true
```

### **Opção 2: Configurar OneDrive Personal (Avançado)**

#### **1. Criar App no Azure Portal**
- Acesse: https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade
- Clique "Novo registro"
- Nome: "Omie Pipeline Personal"
- Tipos de conta: "Contas pessoais da Microsoft apenas"
- URI de redirecionamento: `http://localhost:8080`

#### **2. Obter Credenciais**
- Copie **Application ID** → `client_id`
- Em "Certificados e segredos" → Novo segredo → Copie → `client_secret`

#### **3. Configurar Permissões**
- Em "Permissões de API"
- Adicionar "Files.ReadWrite.All" (OneDrive)

#### **4. Atualizar configuracao.ini**
```ini
[onedrive_personal]
client_id = SEU_CLIENT_ID_AQUI
client_secret = SEU_CLIENT_SECRET_AQUI
redirect_uri = http://localhost:8080
upload_folder = XML_Compactados
base_folder = /
```

#### **5. Implementar OAuth2 Flow**
⚠️ **ATENÇÃO**: OneDrive Personal requer autorização manual do usuário na primeira execução!

## 🚀 **Recomendação: Use OneDrive Business**

### **Vantagens do OneDrive Business (já configurado):**
- ✅ **Funcionando**: Credenciais já configuradas
- ✅ **Automático**: Sem interação manual
- ✅ **Empresarial**: Mais robusto para pipelines
- ✅ **Testado**: Já validado e funcionando

### **Para usar apenas OneDrive Business:**
```ini
[upload_destinations]
# Sistema focado e confiável
onedrive_business_enabled = true
sharepoint_enabled = false  
local_storage_enabled = true
onedrive_personal_enabled = false
```

## 🎯 **Configuração Recomendada Atual**

```ini
[upload_destinations]
# Configuração robusta e testada
onedrive_business_enabled = true
sharepoint_enabled = false
local_storage_enabled = true
onedrive_personal_enabled = false

# Configurações otimizadas
upload_parallel_enabled = true
max_concurrent_uploads = 3
retry_failed_uploads = true
max_retry_attempts = 3
upload_strategy = all
```

### **Resultado:**
- ✅ **Upload para OneDrive Business**: Funcionando
- ✅ **Backup local**: Sempre disponível  
- 🚀 **Performance**: Upload paralelo
- 🔄 **Confiabilidade**: Retry automático

## 💡 **Próximos Passos**

1. **Desabilitar OneDrive Personal** (por enquanto)
2. **Manter OneDrive Business** (já funcionando)
3. **Testar pipeline** com configuração atual
4. **Se necessário**: Implementar OneDrive Personal completo no futuro

**🎊 Sua configuração atual (Business + Local) já oferece redundância e confiabilidade!**
