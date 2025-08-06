-- SQLite
-- Adiciona a coluna para armazenar o caminho do arquivo XML
ALTER TABLE notas ADD COLUMN caminho_arquivo TEXT;

-- Adiciona a coluna para marcar se o XML foi baixado novamente
ALTER TABLE notas ADD COLUMN baixado_novamente INTEGER DEFAULT 0;

ALTER TABLE notas ADD COLUMN xml_vazio INTEGER DEFAULT 0;