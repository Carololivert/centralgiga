# API SGP — Referência de Endpoints

Base: `https://giganetwireless.sgp.net.br`  |  Auth: Token/App no corpo (bypassa 2FA)  |  Coleção Postman oficial da TSMX.

Gerado a partir da coleção do Postman. Use como mapa; os parâmetros exatos ficam na coleção.


## Central Assinante

| Método | Endpoint | Descrição |
|---|---|---|
| POST | `/api/central/contratos` | Contrato - Listar |
| POST | `/api/central/verificaacesso/` | Serviço Internet – Verificar disponibilidade |
| POST | `/api/central/extratouso/` | Serviço Internet – Extrato de Tráfego |
| POST | `/api/central/promessapagamento/` | Contrato – Liberação por Confiança |
| POST | `/api/central/chamado/list/` | Chamado – Listar |
| POST | `/api/central/tipoocorrencia/list/` | Tipos de Ocorrência – Listar |
| POST | `/api/central/chamado/` | Chamado – Criar |
| POST | `/api/central/chamado/update/{os_id}/` | Chamado – Atualizar |
| POST | `/api/central/chamado/{os_id}/anexo/add/` | Chamado – Adicionar Anexo |
| POST | `/api/central/chamado/{os_id}/anotacao` | Ordem de Serviço – Adicionar Anotação |
| POST | `/api/central/notafiscal/list/` | Nota Fiscal – Listar |
| POST | `/api/central/nfcom/list` | NFCom - Listar |
| POST | `/api/central/nfcom/print/{{numero_nota}}` | NFCom - Baixar |
| POST | `/api/central/nfcom/enviar/{{id_nota}}` | NFCom - Enviar |
| POST | `/api/central/nfse/list/` | NFSe – Listar |
| POST | `/api/central/nfse/enviar/{{id_nota}}` | NFSe - Enviar |
| POST | `/api/central/titulos/` | Fatura – Listar |
| POST | `/api/central/fatura2via/` | Fatura – Segunda via |
| POST | `/api/central/pagamento/pix/{id_titulo}` | Fatura – Gerar PIX |
| POST | `/api/central/envia2via/` | Fatura – Enviar |
| POST | `/api/central/pagamento/cartao/{titulo_id}` | Fatura - Pagar via Cartão de Crédito |
| POST | `/api/central/pagamento/cartao/{titulo_id}/debito/` | Fatura - Pagar via Cartão de Débito |
| POST | `/api/central/pagamento/checkout/{titulo_id}/cartao/` | Fatura - Pagar via Cartão Checkout |
| POST | `/api/centralapp/gatewaycartao/list/` | Gateway Cartão - Listar |
| POST | `/api/centralapp/cadastrarcartao/` | Cartão de Crédito - Cadastrar |
| DELETE | `/api/centralapp/deletecartao/{id_cartao}/` | Cartão de Crédito - Delete |
| POST | `/api/centralapp/cartao/{id_cartao}/cobrancarecorrente/add/` | Cobrança Recorrente - Cadastrar |
| POST | `/api/centralapp/cartao/{id_cartao}/cobrancarecorrente/delete/` | Cobrança Recorrente - Delete |
| GET | `/api/centralapp/declaracao/quitacao/2026/` | Declaração de Quitação - Baixar |
| POST | `/api/centralapp/assinaturas/{id_assinatura/detail/` | Assinatura - Detalhe |
| POST | `/api/centralapp/assinaturas/list` | Assinaturas - Listar |
| GET | `/api/centralapp/contrato/print/{tipo}/` | Contrato - PDF |
| GET | `/api/centralapp/avisos/servico/list/` | Avisos - Listar |

## Remessa / Retorno

| Método | Endpoint | Descrição |
|---|---|---|
| POST | `/api/banco/remessa/download/` | Download Remessa |
| POST | `/api/banco/retorno/upload/` | Upload Retorno |

## FTTH

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/fttx/olt/list/` | Listar OLT |
| GET | `/api/fttx/olt/{olt_id}/pon/list/` | Listar PON |
| GET | `/api/fttx/olt/{olt_id}/onu/list/` | Listar ONU por OLT |
| GET | `/api/fttx/onu/list/` | Listar ONU |
| GET | `/api/fttx/olt/pon/{OLT_ID}/splitter/list/` | Listar CTO utilizadas na OLT |
| GET | `/api/fttx/splitter/{cto_id}/onu/all/` | Listar ONUs vinculadas a CTO |
| GET | `/api/fttx/splitter/{id}/` | Listar CTO |
| GET | `/api/fttx/splitter/all/` | Listar todas CTO |
| GET | `/api/fttx/olt/{olt_id}/unauth/` | Listar ONUs não autorizadas |
| POST | `/api/fttx/olt/{olt_id}/auth/` | Autorizar ONU |
| GET | `/api/fttx/onu/{id_onu}/reset/` | Resetar ONU |
| GET | `/api/fttx/olt/{olt_id}/onu/export/` | Exportar ONU |
| GET | `/api/fttx/onu/{id_onu}/info/` | ONU Info |
| GET | `/api/fttx/onu/{id_onu}/` | ONU Detalhe |
| POST | `/api/fttx/onu/{onu_id}/edit/` | Alterar ONU |
| GET | `/api/fttx/onu/{id_onu}/deauth/` | Remover ONU |
| POST | `/api/fttx/onu/{id_onu}/deauth/` | Remover ONU |
| GET | `/api/fttx/onu/{identificador_onu}/wifi/` | ONU Wifi |
| GET | `/api/fttx/onu/{identificador_onu}/wan/` | ONU WAN |
| GET | `/api/fttx/onu/{IDENTIFICADOR_ONU}/cmd/{CMD_ID}/` | ONU CMD |
| POST | `/api/fttx/onu/{IDENTIFICADOR_ONU}/cmd/{CMD_ID}/` | ONU CMD |
| GET | `/api/fttx/onu/{IDENTIFICADOR_ONU}/tl1/cmd/` | ONU TL1 CMD |
| GET | `/api/fttx/onu/history/` | ONU Histórico |
| POST | `/api/fttx/splitter/add/` | Cadastrar CTO |
| GET | `/api/fttx/onutemplate/list/` | ONU Template |
| GET | `/api/fttx/onutype/list/` | ONU Tipo |
| GET | `/api/fttx/onumode/list/` | ONU Modo |
| GET | `/api/fttx/service/list/` | Serviços |
| POST | `/ws/fttx/splitter/service/add/` | Adicionar CTO ao Serviço |

## Estoque

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/estoque/empresa/list/` | Empresa – Listar |
| GET | `/api/estoque/fornecedor/list/` | Fornecedor – Listar |
| GET | `/api/estoque/categoria/list/?nome=` | Categoria – Listar |
| GET | `/api/estoque/fabricante/list/` | Fabricante – Listar |
| GET | `/api/estoque/ncm/list/` | NCM – Listar |
| GET | `/api/estoque/kitinstalacao/list/` | Kit de Instalação – Listar |
| GET | `/api/estoque/kitinstalacaoproduto/list/` | Produtos de Kit – Listar |
| GET | `/api/estoque/comodato/list/` | Comodato de Cliente – Listar |
| GET | `/api/estoque/comodatoitens/list/` | Itens da Comodato – Listar |
| GET | `/api/estoque/venda/list/` | Venda de Cliente – Listar |
| GET | `/api/estoque/vendaitens/list/` | Itens da Venda – Listar |
| GET | `/api/estoque/lancamento/list/` | Lançamento – Listar |
| GET | `/api/estoque/lancamentoitem/list/` | Itens do Lançamento – Listar |
| GET | `/api/estoque/estoque/list/` | Local de Estoque – Listar |
| GET | `/api/estoque/estoque_agregado_referencias/list/` | Saldo – Listar |
| GET | `/api/estoque/produto/list/` | Produto – Listar (Quantitativos) |
| GET | `/api/estoque/produto/list/all/` | Produto – Listar (Cadastrados) |
| GET | `/api/estoque/unidademedida/list/` | Unidades de Medidas - Listar |
| GET | `/api/estoque/compra/list/` | Compras - Listar |
| GET | `/api/estoque/compraitens/list/` | Itens da Compra - Listar |
| GET | `/api/estoque/transferencia/list/` | Transferências - Listar |
| POST | `/api/estoque/lancamentoitem/create/` | Lançamento – Criar |
| POST | `/api/estoque/lancamentoitem/estorno/` | Estorno – Atualizar |
| POST | `/api/estoque/produto/create/` | Produto - Cadastrar |
| POST | `/api/estoque/produto/{produto_id}/update/` | Produto - Alterar |
| POST | `/api/estoque/compra/create/` | Compra - Cadastrar |
| POST | `/api/estoque/transferencia/create/` | Transferência - Cadastrar |
| POST | `/api/ura/produtonfe_produtoestoque/vincular/` | Vincular Produto NFe X Produto Estoque |
| PATCH | `/api/ura/produtonfe_produtoestoque/vincular/` | Vincular Produto NFe X Produto Estoque  Patch |
| POST | `/api/ura/compra/nfe/` | Compra - NFe |
| POST | `/api/estoque/fornecedor/create/` | Fornecedor - Cadastrar |
| POST | `/api/estoque/fornecedor/<fornecedor_id>/update/` | Fornecedor - Alterar |

## Termo de Aceite

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/contrato/termoaceite/{idcontrato}/` | Termo Exibir |
| POST | `/api/contrato/termoaceite/{idcontrato}` | Termo Aceitar |

## URA

| Método | Endpoint | Descrição |
|---|---|---|
| POST | `/api/ura/clientes/` | Cliente – Listar |
| POST | `/api/ura/listacliente/` | Cliente – Listagem Resumida |
| POST | `/api/ura/consultacliente/` | Cliente – Consultar |
| POST | `/api/ura/clientes/semfatura/` | Cliente - Sem Fatura |
| POST | `/api/ura/contato/add/` | Contato – Criar |
| POST | `/api/ura/viabilidade/` | Viabilidade – Consultar |
| GET | `/api/ura/viabilidadeinstalacao` | Viabilidade – Consultar via Gateway |
| POST | `/api/ura/listacontrato/` | Contrato – Listar |
| POST | `/api/ura/contrato/edit/` | Contrato – Atualizar |
| GET | `/api/contratos/print/{tipo_contrato}` | Contrato – Imprimir |
| POST | `/api/ura/liberacaopromessa/` | Contrato – Liberação por Confiança |
| POST | `/api/ura/verificaacesso/` | Serviço Internet – Verificar disponibilidade |
| GET | `/api/ura/portador/` | Portador – Listar |
| POST | `/api/ura/contrato/status/motivos/` | Motivos de Status – Listar |
| POST | `/api/ura/contrato/status/edit/` | Status do Contrato – Atualizar |
| POST | `/api/ura/cliente/servico/senha/edit/` | Senha do Serviço – Atualizar |
| GET | `/api/ura/cpemanage/` | CPE Manage – Consultar |
| POST | `/api/ura/cpemanage/` | CPE Manage – Atualizar |
| GET | `/api/ura/consultaplano/` | Plano – Listar |
| GET | `/api/model/feriado/` | Feriado – Listar |
| GET | `/api/ura/classificacoes/list/` | Classificação - Listar |
| POST | `/api/ura/configuracoes/` | Configurações (Variáveis) – Listar |
| POST | `/api/ura/notificacaosistema/` | Notificação no Sistema – Criar |
| POST | `/api/ura/ocorrencia/list/` | Ocorrência – Listar |
| POST | `/api/ura/ordemservico/list/` | Ordem de Serviço – Listar |
| GET | `/api/ura/ocorrencia/metodo/list/` | Método de Ocorrência – Listar |
| POST | `/api/ura/tecnicos/` | Técnico – Listar |
| POST | `/api/ura/chamado/` | Chamado – Criar |
| POST | `/api/ura/audio/add/` | Chamado – Anexar Áudio |
| POST | `/api/ura/pops/` | POP – Listar |
| POST | `/api/ura/empresas/` | Empresa – Listar |
| POST | `/api/ura/fornecedores/` | Fornecedor – Listar |
| POST | `/api/ura/contas/tiposdocumentos/` | Tipo de Documento (Conta) – Listar |
| POST | `/api/ura/contas/{tipo}/` | Conta à Pagar/Receber – Listar |
| POST | `/api/ura/planoscontas/` | Plano de Contas – Listar |
| POST | `/api/ura/pontosrecebimentos/` | Ponto de Recebimento – Listar |
| POST | `/api/ura/titulos/` | Fatura – Listar |
| POST | `/api/ura/fatura2via/` | Fatura – Segunda via |
| POST | `/api/ura/pagamento/pix/{fatura}` | Fatura – Gerar PIX |
| POST | `/api/ura/enviafatura/` | Fatura – Enviar |
| POST | `/api/banco/titulo/{fatura_id}/baixar/` | Fatura – Liquidar |
| POST | `/api/banco/titulo/{fatura_id}/estornar/` | Fatura – Estornar |
| POST | `/api/banco/titulo/{fatura_id}/pagamento/list` | Fatura – Listar lançamentos de caixa (Liquidação parcial) |
| POST | `/api/banco/titulo/{fatura_id}/cancelar/` | Fatura – Cancelar |
| POST | `/api/banco/titulo/{fatura_id}/descancelar/` | Fatura – Descancelar |
| POST | `/api/ura/cliente/mensalidade/avulsa/add/` | Fatura – Gerar Mensalidade |
| POST | `/api/ura/cliente/titulo/avulso/add/` | Fatura - Gerar Título |
| POST | `/api/ura/acordopagamento` | Fatura – Gerar Acordo de Pagamento |
| POST | `/api/ura/nfe/list/` | NFe - Listar |
| POST | `/api/ura/nfe/importar/` | NFe - Importar |
| POST | `/api/ura/nfe/enviar/{{id_nota}}` | NFe - Enviar |
| POST | `/api/ura/nas/list/` | NAS - Listar |
| GET | `/api/sms/gateway/list/` | SMS - Gateways |
| GET | `/api/sms/send/` | SMS - Enviar |
| GET | `/api/ura/manutencao/list/` | Manutenção - Listar |
| POST | `/api/ura/manutencao/add/` | Manutenção - Cadastrar |
| POST | `/api/ura/manutencao/edit/` | Manutenção - Alterar |
| POST | `/api/ura/manutencao/delete/` | Manutenção - Deletar |
| GET | `/api/ura/ap/list/` | AP - Listar |
| GET | `/api/ura/fonte/list/` | Fonte - Listar |
| GET | `/api/ura/switch/list/` | Switch - Listar |
| GET | `/api/ura/documento/consulta/gateway/{id_gateway}/?documento=&uf=&adicionais=` | Proteção de Crédito - Consulta Documento |
| GET | `/api/ura/consulta/adicionais/gateway/{id_gateway}/?tipo_pessoa` | Proteção de Crédito - Adicionais |
| GET | `/api/ura/gatewaysserasa/list` | Proteção de Crédito - Listar Gateways |
| POST | `/api/ura/cliente/anotacao/add` | Anotações - Adicionar |
| GET | `/api/ura/cliente/anotacao/list` | Anotações - Listar/Consultar |
| POST | `/api/ura/cliente/anotacao/{id}/edit` | Anotações - Atualizar |
| POST | `/api/ura/cliente/anotacao/{id}/remove/` | Anotação - Remover |
| GET | `/api/ura/listgatewaymapa` | Mapa FTTH - Listar Gateways |

## CRM

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/crm/cliente/{{cliente_id}}/` | Consulta Cliente - Cliente ID |
| GET | `/api/crm/cliente/?cpfcnpj` | Consulta Cliente - CPFCNPJ |
| GET | `/api/crm/cliente/{{cliente_id}}/contratos/` | Consulta Contratos - Por Cliente ID |
| GET | `/api/crm/cliente/contratos/?cpfcnpj` | Consulta Contratos - Por CPFCNPJ do Cliente |
| POST | `/api/crm/cliente/F` | Cliente - Cadastrar Pessoa Física |
| POST | `/api/crm/cliente/J` | Cliente - Cadastrar Pessoa Jurídica |
| POST | `/api/crm/cliente/E` | Cliente - Cadastrar Pessoa Estrangeira |
| POST | `/api/crm/cliente/EJ` | Cliente - Cadastrar Pessoa Jurídica Estrangeira |
| POST | `/api/crm/cliente/{{cliente_id}}/contratos` | Contrato - Cadastro por Cliente ID |
| POST | `/api/crm/cliente/contratos/?cpfcnpj` | Contrato - Cadastro por CPFCNPJ Cliente |
| POST | `/api/crm/cliente/{{cliente_id}}/status/` | Status CRM - Alterar por Cliente ID |
| POST | `/api/crm/cliente/status/?cpfcnpj` | Status CRM - Alterar por Cliente CPFCNPJ |

## Pré-Cadastro

| Método | Endpoint | Descrição |
|---|---|---|
| POST | `/api/precadastro/plano/list` | Plano – Listar |
| POST | `/api/precadastro/vencimento/list` | Vencimento – Listar |
| POST | `/api/precadastro/vendedor/list` | Vendedor – Listar |
| POST | `/api/precadastro/F` | Pré-Cadastro – Cadastrar PF |
| POST | `/api/precadastro/J` | Pré-Cadastro – Cadastrar PJ |

## RADIUS

| Método | Endpoint | Descrição |
|---|---|---|
| POST | `/ws/radius/radacct/list/all/` | Login PPPoE – Listar |
| POST | `/ws/radius/service/status/` | Login PPPoE – Detalhar Status |
| POST | `/ws/radius/disconnect/` | Login PPPoE – Desconectar |
| POST | `/ws/radius/{param}/list/` | Radius – Check Replies |
| GET | `/ws/radius/log/` | Radius – Log |

## Ordem de Serviço

| Método | Endpoint | Descrição |
|---|---|---|
| POST | `/api/os/list/` | Ordens de Serviço |
| POST | `/api/os/list/id/{os_id}` | Ordem de Serviço por ID |
| POST | `/api/os/list/total/` | Ordens de Serviço Total |
| POST | `/api/os/update/id/{os_id}/` | Alterar Ordem de Serviço |
| POST | `/api/os/acaminho/id/{os_id}/` | Ordem de Serviço - A caminho |
| GET | `/api/os/print/id/{os_id}/` | Imprimir Ordem de Serviço |
| PUT | `/api/os/imagem/id/{os_id}/add/` | Ordem de Serviço - Anexar Imagem |
| POST | `/api/os/{os_id}/imagem/edit/` | Ordem de Serviço - Alterar descrição da imagem |
| POST | `/api/os/{os_id}/imagem/detail/` | Ordem de Serviço - Imagem |
| GET | `/api/os/imagem/id/{os_id}/list/` | Ordem de Serviço - Imagens |
| GET | ` /api/os/imagem/{anexo_id}` | Ordem de Serviço - Visualizar Anexo por ID |
| GET | `/api/os/imagem/{imagem_id}/delete/` | Ordem de Serviço - Remover Imagem |
| POST | `/api/os/servico/update/id/{os_id}/` | Ordem de Serviço - Alterar Serviço |
| POST | `/api/os/anotacoes/list/id/{os_id}/` | Ordem de Serviço - Anotações |
| POST | `/api/os/anotacoes/add/id/{os_id}/` | Ordem de Serviço - Cadastrar Anotação |
| POST | `/api/os/ocorrencia/comentario/list/id/{os_id}/` | Ordem de Serviço - Comentários (Ocorrência) |
| POST | `/api/os/ocorrencia/comentario/add/id/{os_id}/` | Ordem de Serviço - Cadastrar Comentário (Ocorrência) |
| GET | `/api/os/{os_id}/checklist/list/` | Ordem de Serviço - Checklist |
| POST | `/api/os/checklist/{checklist_id}/toggle/` | Ordem de Serviço - Marcar/Desmarcar Checklist |
| GET | `/api/os/{os_id}/comentario/list/` | Ordem de Serviço - Comentários |
| POST | `/api/os/{os_id}/comentario/add/` | Ordem de Serviço - Cadastrar Comentário |
| POST | `/ws/os/{os_id}/comentario/delete/` | Ordem de Serviço - Excluir Comentário |
| GET | `/api/os/ocorrencia/motivo/list/` | Motivos |
| GET | `/api/os/ocorrencia/metodo/list/` | Métodos |
| GET | `/api/os/ocorrencia/tipo/list/` | Tipos |
| GET | `/api/os/ocorrencia/setor/list/` | Setores |

## Suporte

| Método | Endpoint | Descrição |
|---|---|---|
| POST | `/api/suporte/service/update/{servico_id}/` | Serviço - Alterar |
| POST | `/api/servico/generico` | Serviço Genérico - Criar |
| DELETE | `/api/servico/generico/{id}` | Serviço Genérico - Deletar |
| POST | `/api/suporte/contrato/list/` | Contratos |
| PUT | `/api/suporte/cliente/{cliente_id}/documento/add/` | Cadastrar Cliente Documento |
| POST | `/api/suporte/cliente/{cliente_id}/documento/edit/` | Alterar Cliente Documento |
| POST | `/api/suporte/cliente/{cliente_id}/documento/detail/` | Cliente Documento |
| GET | `/api/suporte/cliente/{cliente_id}/documento/list/` | Cliente Documentos |
| GET | `/api/suporte/cliente/{documento_id}/documento/delete/` | Remover Cliente Documento |

## Outros

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/auth/info/` | Informações do usuário |

## Gerenciador CPE

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/cpemanager/servico/{id_servico}/infodetail` | CPE - Detalhes |
| POST | `/api/cpemanager/servico/{id_servico}/sync/` | CPE - Sincronizar WAN |
| POST | `/api/cpemanager/servico/{id_servico}/wifi/import/` | CPE - Importar Wifi |
| POST | `/api/cpemanager/servico/{id_servico}/wifi/set/` | CPE - Definir Wifi |
| POST | `/api/cpemanager/servico/{id_servico}/pppoe/` | CPE - Configurar Wan |
| POST | `/api/cpemanager/servico/{id_servico}/command/ping/` | CPE - Ping |
| POST | `/api/cpemanager/servico/{id_servico}/command/speedtest/` | CPE - SpeedTest |
| POST | `/api/cpemanager/servico/{id_servico}/command/clear/` | CPE - Remover Dados do SGP |
| POST | `/api/cpemanager/servico/{id_servico}/command/boot/` | CPE - Reboot |
| GET | `/api/cpemanager/servico/{id_servico}/wifi/list/` | CPE - Wifi List |
| POST | `/api/cpemanager/servico/{id_servico}/wifi/update/` | CPE - Atualizar dados Wifi |
| POST | `/api/cpemanager/servico/{id_servico}/update/field/?param=InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.PreSharedKey.1.KeyPassphrase&value=123123456` | CPE - Atualizar Campo |