
SELECT * FROM notas WHERE anomesdia = (SELECT MAX(anomesdia) FROM notas);

UPDATE notas SET xml_baixado = 0 WHERE anomesdia between 20250801 and 20250810
SELECT * FROM notas WHERE anomesdia between 20250801 and 20250810
SELECT * FROM notas WHERE anomes = 202507
SELECT * FROM notas WHERE anomesdia = 20250816;
SELECT * from notas where dEmi = '16/08/2025'
SELECT* from notas where dEmi = '08/08/2025'
SELECT * from notas where nNF in ('01431283', '01431528', '01431530', '01431561', '01431564', '01431822', '01431935', '01432320', '01432576', '01433546', '01433565', '01433566', '01433567', '01436370', '01437480', '01437619', '01437645', '01437994', '01438151', '01438596', '01438690', '01438931', '01439091', '01440951', '01441109')
select * from notas WHERE anomes in (202507,202506)
UPDATE notas SET xml_baixado = 0 WHERE anomes in (202507,202506)
Update notas SET xml_baixado = 0 where nNF in ('01431283', '01431528', '01431530', '01431561', '01431564', '01431822', '01431935', '01432320', '01432576', '01433546', '01433565', '01433566', '01433567', '01436370', '01437480', '01437619', '01437645', '01437994', '01438151', '01438596', '01438690', '01438931', '01439091', '01440951', '01441109')


-- Contagem total de notas
SELECT COUNT(*) AS total_notas FROM notas;

-- Notas duplicadas por chave
SELECT cChaveNFe, COUNT(*) as qtd
FROM notas
GROUP BY cChaveNFe
HAVING qtd > 1;

-- Notas baixadas
SELECT * FROM notas WHERE xml_baixado = 1;

-- Notas pendentes
SELECT * FROM notas WHERE xml_baixado = 0;

-- Notas com erro
SELECT * FROM notas WHERE erro = 1;

-- Correcao Notas com erro
SELECT * FROM notas WHERE erro = 1;
UPDATE notas
SET baixado_novamente = 1,
    erro = 0
WHERE erro = 1;
-- Verificação da correççao
SELECT cChaveNFe, cRazao, xml_baixado, xml_vazio, baixado_novamente, erro, mensagem_erro
FROM notas
WHERE baixado_novamente = 1

-- Notas com XML vazio
SELECT * FROM notas WHERE xml_vazio = 1;
-- Correção xml vazio
UPDATE notas
SET xml_vazio = 0
WHERE xml_vazio = 1

-- Notas emitidas em julho de 2025 (faixa de anomesdia)
SELECT * FROM notas WHERE anomesdia BETWEEN 20250701 AND 20250731;


-- Total de notas emitidas por dia
SELECT anomesdia, COUNT(*) AS qtd_notas
FROM notas
GROUP BY anomesdia
ORDER BY anomesdia DESC;

-- Valor total emitido por mês (supondo que anomesdia tem formato YYYYMMDD)
SELECT SUBSTR(CAST(anomesdia AS TEXT), 1, 6) AS ano_mes, SUM(vNF) AS total_mes
FROM notas
GROUP BY ano_mes
ORDER BY ano_mes DESC;

-- Valor médio das notas baixadas
SELECT AVG(cChaveNFe) AS media_baixadas
FROM notas
WHERE xml_baixado = 1;

-- Quantidade e valor de notas baixadas X pendentes
SELECT
  SUM(CASE WHEN xml_baixado = 1 THEN 1 ELSE 0 END) AS baixadas,
  SUM(CASE WHEN xml_baixado = 0 THEN 1 ELSE 0 END) AS pendentes,
  SUM(CASE WHEN xml_baixado = 1 THEN vNF ELSE 0 END) AS valor_baixado,
  SUM(CASE WHEN xml_baixado = 0 THEN vNF ELSE 0 END) AS valor_pendente
FROM notas;

-- Percentual de notas baixadas
SELECT
  100.0 * SUM(CASE WHEN xml_baixado = 1 THEN 1 ELSE 0 END) / COUNT(*) AS pct_baixadas
FROM notas;

-- Top 10 clientes por quantidade de notas fiscais únicas emitidas
SELECT 
    cRazao, 
	cnpj_cpf,
    COUNT(DISTINCT nNF) AS qtd_notas_unicas
FROM notas
GROUP BY cRazao
ORDER BY qtd_notas_unicas DESC
LIMIT 10;

-- Top 10 maiores notas do período
SELECT * FROM notas
ORDER BY vNF DESC
LIMIT 10;

-- Evolução diária do valor baixado (últimos 30 dias)
SELECT 
    dEmi, 
    SUM(CASE WHEN xml_baixado = 1 THEN 1 ELSE 0 END) AS total_baixado
FROM 
    notas
WHERE 
    xml_baixado = 1
    AND anomesdia BETWEEN 
        (SELECT MAX(anomesdia) - 30 FROM notas)
        AND (SELECT MAX(anomesdia) FROM notas)
GROUP BY 
    anomesdia
ORDER BY 
    anomesdia DESC, total_baixado DESC;



-- Notas sem cliente identificado
SELECT * FROM notas WHERE cRazao IS NULL OR TRIM(cRazao) = '';

-- Baixadas com erro (casos raros)
SELECT * FROM notas WHERE xml_baixado = 1 AND erro = 1;

-- Distribuição do status por cliente (top 5)
SELECT cRazao,
  SUM(CASE WHEN xml_baixado = 1 THEN 1 ELSE 0 END) AS baixadas,
  SUM(CASE WHEN xml_baixado = 0 THEN 1 ELSE 0 END) AS pendentes
FROM notas
GROUP BY cRazao
ORDER BY baixadas DESC
LIMIT 10;

-- Buscar notas pendentes (se já criou a view)
SELECT * FROM vw_notas_pendentes;

-- Resumo diário (view)
SELECT * FROM vw_resumo_diario WHERE anomesdia >= 20250701;

-- Notas recentes
SELECT * FROM vw_notas_com_erro;

-- Faturamento por dia e status
SELECT dEmi,
  SUM(CASE WHEN xml_baixado = 1 THEN vNF ELSE 0 END) AS valor_baixado,
  SUM(CASE WHEN xml_baixado = 0 THEN vNF ELSE 0 END) AS valor_pendente
FROM notas
GROUP BY dEmi
ORDER BY dEmi DESC;

-- Dias com maior número de pendências
SELECT dEmi, COUNT(*) as qtd_pendentes
FROM notas
WHERE xml_baixado = 0
GROUP BY dEmi
ORDER BY qtd_pendentes DESC
LIMIT 5;

-- Total, baixadas, pendentes, erro, valor médio e maior valor
SELECT
  COUNT(*) AS total,
  SUM(CASE WHEN xml_baixado = 1 THEN 1 ELSE 0 END) AS baixadas,
  SUM(CASE WHEN xml_baixado = 0 THEN 1 ELSE 0 END) AS pendentes,
  SUM(CASE WHEN erro = 1 THEN 1 ELSE 0 END) AS erros,
  ROUND(AVG(vNF), 2) AS media_valor,
  MAX(vNF) AS maior_valor
FROM notas;


SELECT COUNT(*) AS total_notas FROM notas
Where anomesdia >= 20250701

