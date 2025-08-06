--Comando para acompanhar como esta o andamento do download dos arquivos
select n.dEmi
, count(n.cChaveNFe) as total
, (select count(n2.cChaveNFe) from notas n2 where 	n.dEmi = n2.dEmi and n2.xml_baixado = 1) as total_baixado 
from notas n 
GROUP by n.dEmi 
order by dEmi ASC