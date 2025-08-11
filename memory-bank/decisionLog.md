# Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-08-09 | Implementação bem-sucedida do sistema flexível de upload multi-repositório mantendo compatibilidade com sistema legado | O sistema detecta automaticamente se o arquivo upload_config.ini existe e usa o UploadManager flexível, caso contrário utiliza o sistema legado OneDrive. Isso garante que a pipeline continue funcionando mesmo sem configuração adicional, atendendo o requisito de não quebrar funcionalidade existente. |
| 2025-08-09 | Consolidação completa de arquivos de configuração em um único arquivo configuracao.ini | Migrou todas as configurações de .env, upload_config.ini e configuracao.ini para um único arquivo configuracao.ini. O sistema detecta automaticamente se deve usar o sistema flexível (baseado na existência da seção upload_destinations) ou o sistema legado OneDrive. Mantém compatibilidade total e remove duplicação de variáveis de ambiente. |
| 2025-08-09 | Implementação completa do OneDrive Personal com autorização OAuth2 para pasta específica "OMIE - Notas" | Usuário solicitou salvamento na pasta "OMIE - Notas" do OneDrive Personal. Implementamos handler completo com Microsoft Graph API, script de autorização OAuth2, e configuração específica para a pasta desejada. Mantém compatibilidade com outros destinos. |
