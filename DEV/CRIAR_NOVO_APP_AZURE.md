🆘 SOLUÇÃO ALTERNATIVA: Criar Novo App Azure AD
==============================================

Se você não conseguir acessar/corrigir o aplicativo atual, podemos criar um novo.

📋 PASSO A PASSO PARA CRIAR NOVO APP:

1. 🌐 Acesse o Azure Portal
   - URL: https://portal.azure.com
   - Login: Conta Microsoft PESSOAL (a mesma do OneDrive)

2. 🆕 Criar Novo App Registration
   - Azure Active Directory → App registrations → "New registration"
   
   - Name: "Omie Pipeline OneDrive Personal v2"
   - Supported account types: "Accounts in any organizational directory and personal Microsoft accounts"
   - Redirect URI: deixe em branco por enquanto
   - Clique "Register"

3. 📝 Configurar o App
   Após criado, anote:
   - Application (client) ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   
   Em "Certificates & secrets":
   - New client secret → Description: "Pipeline Secret" → Add
   - Anote o Value (não o ID!)

4. ⚙️ Configurar Authentication
   - No menu Authentication → Add a platform → Mobile and desktop applications
   - Adicione estes Redirect URIs:
     ✅ http://localhost:8080/callback
     ✅ https://login.microsoftonline.com/common/oauth2/nativeclient
     ✅ https://login.live.com/oauth20_desktop.srf
   - Allow public client flows: Yes
   - Save

5. 🔑 Adicionar Permissões API
   - API permissions → Add a permission → Microsoft Graph → Delegated permissions
   - Adicione:
     ✅ Files.ReadWrite.All
     ✅ offline_access
   - Save

6. 🔄 Atualizar Configuração
   Edite o arquivo configuracao.ini:
   
   [onedrive_personal]
   client_id = SEU_NOVO_CLIENT_ID_AQUI
   client_secret = SEU_NOVO_CLIENT_SECRET_AQUI
   redirect_uri = http://localhost:8080/callback
   upload_folder = OMIE - Notas
   base_folder = /

7. 🚀 Testar
   python auth_onedrive_personal_alt.py

💡 DICA: Se ainda assim não funcionar, o problema pode ser que as contas
Microsoft PESSOAIS têm restrições diferentes das organizacionais.

🆘 ÚLTIMA ALTERNATIVA: Podemos configurar o OneDrive Business (que já está
funcionando 100%) para salvar na pasta "OMIE - Notas" também.
