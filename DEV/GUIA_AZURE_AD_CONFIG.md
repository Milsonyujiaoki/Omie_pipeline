🔧 GUIA: Configurar Redirect URIs no Azure AD
=============================================

PROBLEMA: O erro AADSTS50011 indica que o redirect_uri não está configurado no Azure AD.

📋 PASSO A PASSO PARA CORRIGIR:

1. 🌐 Acesse o Azure Portal
   URL: https://portal.azure.com
   Login: Use sua conta Microsoft PESSOAL (a mesma do OneDrive)

2. 🏗️ Navegue para App Registrations
   - No menu lateral, clique em "Azure Active Directory"
   - No submenu, clique em "App registrations"
   - Procure pelo aplicativo com nome contendo "Omie" ou ID: 56846950-c73f-4c45-9095-6e341bdaafb8

3. ⚙️ Configure Redirect URIs
   - Clique no aplicativo
   - No menu lateral, clique em "Authentication"
   - Na seção "Redirect URIs", clique em "Add URI"
   - Adicione AMBOS os URIs abaixo:
     
     ✅ URI 1: http://localhost:8080/callback
     ✅ URI 2: https://login.microsoftonline.com/common/oauth2/nativeclient
   
   - Clique em "Save" (Salvar)

4. ✅ Configurar Tipo de Aplicativo
   - Na mesma tela "Authentication"
   - Em "Supported account types", certifique-se que está selecionado:
     "Accounts in any organizational directory and personal Microsoft accounts"
   - Em "Allow public client flows", marque como "Yes" (Sim)
   - Clique em "Save"

5. 🔑 Verificar Permissões API
   - No menu lateral, clique em "API permissions"
   - Certifique-se que tem as permissões:
     ✅ Files.ReadWrite.All (Delegated)
     ✅ offline_access (Delegated)
   - Se não tiver, clique em "Add a permission" → Microsoft Graph → Delegated permissions
   - Procure e adicione essas permissões

6. 🚀 Testar Novamente
   - Após salvar, aguarde 1-2 minutos para propagar
   - Execute novamente: python auth_onedrive_personal_alt.py

💡 DICA: Se não conseguir acessar o Azure Portal ou encontrar o aplicativo,
pode ser que precise de permissões de administrador ou o app foi criado 
por outra conta.

🆘 ALTERNATIVA: Se não conseguir acessar o Azure Portal, podemos criar
um novo aplicativo Azure AD com as configurações corretas.
